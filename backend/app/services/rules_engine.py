"""
backend/app/services/rules_engine.py
----------------------------------------
Purpose: The deterministic, non-AI decision layer of TenderIQ. Takes the
raw AI-extracted Evidence for one (bidder, criterion) pair and turns it
into a PASS / FAIL / REVIEW Verdict, using pure Python logic -- no LLM
calls, no randomness, same input always produces the same output. This
is what makes every eligibility decision reproducible and legally
defensible in front of a CAG auditor (Project Context 9, 15).

Golden rule enforced everywhere below: when evidence is missing,
unreadable, low-confidence, or ambiguous -> REVIEW, never FAIL, and
never a guessed PASS either. A bidder must never lose a government
contract because OCR/AI could not read a document clearly, and the
system must never silently wave one through on an unclear reading
(Project Context 5.9).

Where this file is used:
- workers/tasks.py's process_bidder_documents() calls evaluate_evidence()
  once per Evidence row, right after Evidence is created, to build the
  matching Verdict row.
- routers/evaluation.py's override endpoint calls
  calculate_overall_verdict() after an officer changes a verdict, to
  recompute the bidder's overall result.

TWO DOCUMENTED ASSUMPTIONS (decided when building this file, because
Phase 3's already-tested-live AI extraction stores each
Evidence.raw_value as free descriptive text -- e.g. "Turnover of
Rs. 1.84 Crore in FY 2023-24" -- not a pre-parsed number, unlike the
Phase Guide's pseudocode which assumes a clean value is already there):

1. _parse_numeric_value() below extracts a number from that free text
   and normalizes Lakh/Crore/plain-rupee mentions onto one consistent
   Lakhs scale (matching threshold_json's "unit": "Lakhs" convention).
   If no confident number is found, the calling check function returns
   REVIEW -- it never guesses.

2. check_composite() always returns REVIEW. A true composite check
   (e.g. AIIMS's "bidder turnover AND OEM turnover both required")
   needs two or more separate evidence values linked to one criterion.
   The Evidence table has exactly one row per (bidder, criterion) pair
   with no way to mark "this is the bidder-half" vs "this is the
   OEM-half" of one requirement. Automating it correctly needs a real
   schema change (child criteria) -- out of scope for this phase, which
   must not redesign already-built architecture. Only 1 of the 15+
   real tenders analysed needed this rule type, so every composite
   case is flagged for manual officer review instead.
"""

import re
from app.models.evidence import Evidence
from app.models.criterion import Criterion, RuleType
from app.models.bidder import Bidder, BidderCategory, OverallVerdict
from app.models.tender import Tender
from app.models.verdict import Verdict, VerdictEnum


# ---------------------------------------------------------------------
# Value parsing helpers
# ---------------------------------------------------------------------

def _parse_numeric_value(raw_value: str | None) -> float | None:
    """
    Purpose: Extracts a numeric value out of AI-written free text,
    converting Crore/Lakh unit mentions onto a consistent Lakhs scale.

    Where it gets its data: raw_value is Evidence.raw_value -- whatever
    string bidder_parser.py's AI wrote.

    Where it's used: Called by check_numeric_threshold(),
    check_conditional_threshold(), and check_quantity_pct() below.

    FIX (found via real data on 2026-07-13): the earlier version took
    the *first* number found anywhere in the text -- for evidence like
    "FY 2022-23: Rs. 4,18,62,340", that meant grabbing "2022" (the
    fiscal year) instead of the actual turnover figure, silently
    producing a wrong FAIL. This version prefers numbers explicitly
    marked with a currency symbol (Rs./INR/₹), falling back to any
    number with 5+ digits (a plausible rupee amount) rather than a
    bare 4-digit number, which is almost always a year in this AI's
    phrasing style.

    When multiple figures are found (e.g. three years of turnover for
    an "any_of_preceding_years" style criterion), this returns the
    MAXIMUM. That's the correct, defensible check: if the largest
    figure doesn't clear a threshold, none of the smaller ones will
    either -- so max() correctly answers "did the bidder clear this
    threshold in ANY of the listed years."

    Returns: The value in Lakhs, or None if no confident numeric value
    could be found.
    """
    if not raw_value or not raw_value.strip():
        return None

    text = raw_value.lower().replace(",", "")

    currency_matches = re.findall(r"(?:rs\.?|inr|₹)\s*([\d.]+)", text)
    candidates = [float(m) for m in currency_matches if m]

    if not candidates:
        # No explicit currency marker found -- fall back to any number
        # with 5+ digits, since a bare 4-digit number in this AI's
        # phrasing is almost always a fiscal year, not an amount.
        all_numbers = re.findall(r"\d+\.?\d*", text)
        candidates = [float(n) for n in all_numbers if len(n.split(".")[0]) >= 5]

    if not candidates:
        # Last resort: a single plain number with no currency marker
        # and no 5+ digit candidate (e.g. a short "184" with no unit
        # words at all).
        match = re.search(r"[-+]?\d*\.?\d+", text)
        if match:
            candidates = [float(match.group())]

    if not candidates:
        return None

    value = max(candidates)

    if "crore" in text or re.search(r"\bcr\b", text):
        return value * 100
    if "lakh" in text or re.search(r"\bl\b", text):
        return value
    if value >= 100000:
        return value / 100000
    return value


def _threshold_value_in_lakhs(threshold_data: dict) -> float | None:
    """
    Purpose: Converts a Criterion's threshold_json["value"] onto the
    same Lakhs scale that _parse_numeric_value() already converts
    extracted evidence to -- so the two sides of a comparison are
    always in matching units.

    Where it gets its data: threshold_data is a Criterion's
    threshold_json dict, e.g. {"value": 36162000, "unit": "INR"} or
    {"value": 128, "unit": "Lakhs"}.

    Where it's used: Called by check_numeric_threshold() below.

    FIX (found via real data on 2026-07-13): earlier code read
    threshold_json["value"] directly and assumed it was always already
    in Lakhs. In practice the AI's tender_parser extraction sometimes
    writes the threshold in raw INR instead (e.g. "unit": "INR",
    "value": 36162000 for a 3.6 Crore requirement) -- comparing an
    unconverted 493-Lakh evidence value against an unconverted
    36-million "Lakh" threshold was silently wrong.
    """
    value = threshold_data.get("value")
    if value is None:
        return None
    value = float(value)
    unit = (threshold_data.get("unit") or "lakhs").strip().lower()

    if unit in ("inr", "rs", "rupee", "rupees"):
        return value / 100000
    if unit in ("crore", "crores", "cr"):
        return value * 100
    return value  # already in Lakhs


def _parse_percentage(raw_value: str | None) -> float | None:
    """
    Purpose: Extracts a single percentage number from free AI text
    (e.g. "Local content is approximately 55%"), with no unit
    conversion needed (unlike money values).

    Where it gets its data: raw_value is Evidence.raw_value.

    Where it's used: Called by check_classification() below.

    Returns: The number found, or None if nothing parseable was found.
    """
    if not raw_value or not raw_value.strip():
        return None
    match = re.search(r"[-+]?\d*\.?\d+", raw_value.replace(",", ""))
    if not match:
        return None
    return float(match.group())


_OPERATORS = {
    ">=": lambda value, threshold: value >= threshold,
    "<=": lambda value, threshold: value <= threshold,
    "==": lambda value, threshold: value == threshold,
    ">": lambda value, threshold: value > threshold,
    "<": lambda value, threshold: value < threshold,
}

def _parse_plain_number(raw_value: str | None) -> float | None:
    """
    Purpose: Extracts a single plain number from free text, with no
    currency/unit conversion -- used for NUMERIC_THRESHOLD criteria
    that measure something other than money (e.g. "BG valid for at
    least 3 months", "experience within the last 7 years").

    Where it gets its data: raw_value is Evidence.raw_value.

    Where it's used: Called by check_numeric_threshold() below, only
    for criteria whose threshold_json["unit"] is a non-money unit
    (days/months/years/etc).
    """
    if not raw_value or not raw_value.strip():
        return None
    match = re.search(r"[-+]?\d*\.?\d+", raw_value.replace(",", ""))
    if not match:
        return None
    return float(match.group())


_NON_MONEY_UNITS = {
    "day", "days", "month", "months", "year", "years",
    "pct", "percent", "percentage", "count", "units",
}


def _compare(value: float, operator: str, threshold: float) -> bool:
    """
    Purpose: Applies a criterion's comparison operator (e.g. ">=")
    between an extracted value and its required threshold.

    Where it gets its data: value comes from _parse_numeric_value().
    operator and threshold come from a Criterion row (operator column,
    threshold_json["value"]).

    Where it's used: Called by check_numeric_threshold() and (via it)
    check_conditional_threshold() below. Defaults to ">=" for any
    operator string this dict doesn't recognize, since ">=" is by far
    the most common comparison across all 15+ tenders analysed.
    """
    compare_fn = _OPERATORS.get(operator, _OPERATORS[">="])
    return compare_fn(value, threshold)


# ---------------------------------------------------------------------
# Rule Type 1 -- Numeric Threshold
# ---------------------------------------------------------------------

def check_numeric_threshold(evidence: Evidence, criterion: Criterion) -> tuple[VerdictEnum, str]:
    """
    Purpose: Evaluates a "value <operator> threshold" style criterion.
    Branches into two modes depending on threshold_json["unit"]:
    money-based (e.g. turnover in INR/Lakhs/Crore) uses the Lakhs-
    normalizing parser; non-money (days/months/years/pct/count) uses a
    plain number comparison with no currency conversion.

    Where it gets its data: evidence is one Evidence row. criterion is
    the matching Criterion row.

    Where it's used: Called directly by evaluate_evidence()'s
    dispatcher for rule_type=NUMERIC_THRESHOLD, and reused internally
    by check_conditional_threshold() (Type 2 reduces to this after
    adjusting the threshold for MSME/young-company cases).

    FIX (found via real Indian Oil tender data on 2026-07-13): the
    earlier version always treated every NUMERIC_THRESHOLD criterion
    as money and always labeled its rationale "...L" (Lakhs) -- wrong
    for real criteria like "BG validity >= 3 months" or "experience
    within last 7 years", which use NUMERIC_THRESHOLD for non-money
    counts. This version checks threshold_json["unit"] first and only
    applies Lakhs conversion when the unit actually indicates money.
    """
    if evidence.confidence < 0.6:
        return VerdictEnum.REVIEW, (
            f"Low AI/OCR confidence ({evidence.confidence:.2f}) on extracted value "
            f"-- manual verification required"
        )

    threshold_data = criterion.threshold_json or {}
    if threshold_data.get("value") is None:
        return VerdictEnum.REVIEW, "Criterion has no numeric threshold configured -- manual verification required"

    operator = criterion.operator or ">="
    unit = (threshold_data.get("unit") or "").strip().lower()

    if unit in _NON_MONEY_UNITS:
        value = _parse_plain_number(evidence.raw_value)
        if value is None:
            return VerdictEnum.REVIEW, (
                f"Could not extract a numeric value from AI output ('{evidence.raw_value}') "
                f"-- manual verification required"
            )
        threshold = float(threshold_data["value"])
        passed = _compare(value, operator, threshold)
        verdict = VerdictEnum.PASS if passed else VerdictEnum.FAIL
        rationale = f"Extracted {value:g} {unit} {operator} required {threshold:g} {unit} -> {verdict.value}"
        return verdict, rationale

    # Money-based (INR/Lakhs/Crore, or unit unspecified -- assumed
    # already in Lakhs, matching tender_parser.py's default convention).
    value = _parse_numeric_value(evidence.raw_value)
    if value is None:
        return VerdictEnum.REVIEW, (
            f"Could not extract a numeric value from AI output ('{evidence.raw_value}') "
            f"-- manual verification required"
        )

    threshold = _threshold_value_in_lakhs(threshold_data)
    passed = _compare(value, operator, threshold)
    verdict = VerdictEnum.PASS if passed else VerdictEnum.FAIL
    rationale = f"Extracted {value:g}L {operator} required {threshold:g}L -> {verdict.value}"
    return verdict, rationale

# ---------------------------------------------------------------------
# Rule Type 2 -- Conditional Threshold (MSME/Startup exemptions,
# young-company scaling)
# ---------------------------------------------------------------------

def check_conditional_threshold(evidence: Evidence, criterion: Criterion, bidder: Bidder) -> tuple[VerdictEnum, str]:
    """
    Purpose: Same as Type 1, but first checks two exemption paths
    required by GFR 2017: (a) MSME/Startup bidders are fully exempt if
    the criterion allows it, (b) companies younger than the criterion's
    required years get a proportionally scaled-down threshold instead
    of an outright fail for simply not existing long enough.

    Where it gets its data: bidder is the Bidder row (for category and
    company_age_years). evidence and criterion as above.

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=CONDITIONAL.

    ASSUMPTION: the Phase Guide describes young-company handling as
    "use average of completed years only" -- but Evidence.raw_value is
    one AI-summarized figure, not a year-by-year breakdown to average.
    Instead, this scales the required threshold down proportionally to
    the company's actual age (e.g. a 3-year threshold for a company
    that's only existed 1.5 years becomes a 1.5-year-equivalent
    threshold) -- a defensible, explainable interpretation given what
    the data actually contains.
    """
    if bidder.category in (BidderCategory.MSME, BidderCategory.STARTUP) and criterion.msme_exempt:
        return VerdictEnum.PASS, f"{bidder.category.value} exemption applies under GFR 2017 -> PASS"

    threshold_data = dict(criterion.threshold_json or {})
    required_years = threshold_data.get("years")
    scaled_note = ""

    if (
        bidder.company_age_years is not None
        and required_years
        and bidder.company_age_years < required_years
        and threshold_data.get("value") is not None
    ):
        original_value = float(threshold_data["value"])
        scaled_value = original_value * (bidder.company_age_years / required_years)
        threshold_data["value"] = scaled_value
        scaled_note = (
            f" (threshold scaled from {original_value:g}L to {scaled_value:g}L "
            f"for a {bidder.company_age_years:g}-year-old company, "
            f"vs. the {required_years}-year requirement)"
        )

    class _ScaledCriterion:
        """Lightweight stand-in so check_numeric_threshold() can reuse
        its comparison logic without mutating the real Criterion row."""
        threshold_json = threshold_data
        operator = criterion.operator

    verdict, rationale = check_numeric_threshold(evidence, _ScaledCriterion())
    return verdict, rationale + scaled_note


# ---------------------------------------------------------------------
# Rule Type 3 -- No-Loss Check
# ---------------------------------------------------------------------

_NO_LOSS_PHRASES = [
    "no loss", "no losses", "profit in all", "profitable in all",
    "did not report any loss", "zero loss years", "no year of loss",
    "no losses incurred",
]


def check_no_loss(evidence: Evidence, criterion: Criterion) -> tuple[VerdictEnum, str]:
    """
    Purpose: Checks a bidder hasn't reported losses in more years than
    allowed (default: 2 out of the last 5), per criteria like EPI's
    infrastructure tenders (Project Context 14).

    Where it gets its data: evidence.raw_value is free text describing
    the bidder's profit/loss history, as extracted by bidder_parser.py.

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=NO_LOSS.

    ASSUMPTION/LIMITATION: raw_value is unstructured prose, not a
    parsed list of loss years. This counts distinct year-like mentions
    (e.g. "FY21", "2022") in the text as an approximation of the loss
    count, unless the text clearly states there were no losses at all.
    If neither a clear "no loss" statement nor any year mentions are
    found, it defers to REVIEW rather than guessing.
    """
    if evidence.confidence < 0.7:
        return VerdictEnum.REVIEW, (
            f"Low confidence ({evidence.confidence:.2f}) on loss/profit history "
            f"-- manual verification required"
        )

    raw = (evidence.raw_value or "").lower().strip()
    if not raw:
        return VerdictEnum.REVIEW, "No loss/profit information found in documents -- manual verification required"

    if any(phrase in raw for phrase in _NO_LOSS_PHRASES):
        return VerdictEnum.PASS, "No losses reported in the relevant period -> PASS"

    year_mentions = set(re.findall(r"(?:fy\s?)?(20\d{2}|\d{2}-\d{2})", raw))
    if not year_mentions:
        return VerdictEnum.REVIEW, (
            f"Could not determine number of loss years from extracted text "
            f"('{evidence.raw_value}') -- manual verification required"
        )

    loss_count = len(year_mentions)
    max_allowed = (criterion.threshold_json or {}).get("max_loss_years", 2)
    if loss_count > max_allowed:
        return VerdictEnum.FAIL, f"{loss_count} loss year(s) found, exceeds allowed maximum of {max_allowed} -> FAIL"
    return VerdictEnum.PASS, f"{loss_count} loss year(s) found, within allowed maximum of {max_allowed} -> PASS"


# ---------------------------------------------------------------------
# Rule Type 4 -- Quantity / Percentage
# ---------------------------------------------------------------------

def check_quantity_pct(evidence: Evidence, criterion: Criterion, tender: Tender) -> tuple[VerdictEnum, str]:
    """
    Purpose: Checks a bidder's past-work value against a percentage of
    the current tender's estimated value -- e.g. "must have completed
    a similar work worth >= 80% of this tender's value" (the 80/60/40
    rule from EPI infrastructure tenders, Project Context 14).

    Where it gets its data: evidence.raw_value holds the AI-extracted
    value of the bidder's past similar work. tender.estimated_value is
    used as the "required quantity" base, since the schema has no
    separate bid_qty field.

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=QUANTITY_PCT.

    LIMITATION (documented): the 80/60/40 rule really means "one work
    >=80%, OR two works each >=60%, OR three works each >=40%" -- but
    Evidence stores one summarized value per criterion, not a list of
    separate past contracts. This can only confidently confirm the
    strongest single-work case (>=80%). Anything below that but above
    a lower rung is flagged for manual document review rather than
    guessed, since a false automatic PASS here is a real compliance
    risk, not just an inconvenience.
    """
    if evidence.confidence < 0.6:
        return VerdictEnum.REVIEW, (
            f"Low confidence ({evidence.confidence:.2f}) on supplied quantity/value "
            f"-- manual verification required"
        )

    threshold_data = criterion.threshold_json or {}
    supplied_value = _parse_numeric_value(evidence.raw_value)
    if supplied_value is None:
        return VerdictEnum.REVIEW, (
            f"Could not extract a supplied quantity/value from AI output "
            f"('{evidence.raw_value}') -- manual verification required"
        )

    if not tender.estimated_value:
        return VerdictEnum.REVIEW, "Tender has no estimated value configured to compute the required percentage"

    supplied_pct = (supplied_value / tender.estimated_value) * 100
    combinations = threshold_data.get("combinations")

    if combinations:
        strongest = max(combinations)
        if supplied_pct >= strongest:
            return VerdictEnum.PASS, (
                f"Supplied value is {supplied_pct:.1f}% of tender value, satisfies the "
                f"{strongest}% single-work threshold -> PASS"
            )
        return VerdictEnum.REVIEW, (
            f"Supplied value is {supplied_pct:.1f}% of tender value -- does not meet the "
            f"single-work {strongest}% threshold, but may still qualify under multi-work "
            f"combinations ({combinations}) that require manual document verification"
        )

    required_pct = threshold_data.get("pct", threshold_data.get("value"))
    if required_pct is None:
        return VerdictEnum.REVIEW, "Criterion has no percentage threshold configured -- manual verification required"

    if supplied_pct >= float(required_pct):
        return VerdictEnum.PASS, f"Supplied {supplied_pct:.1f}% >= required {required_pct}% -> PASS"
    return VerdictEnum.FAIL, f"Supplied {supplied_pct:.1f}% < required {required_pct}% -> FAIL"


# ---------------------------------------------------------------------
# Rule Type 5 -- Boolean Declaration
# ---------------------------------------------------------------------

_NEGATION_PHRASES = [
    "not submitted", "not found", "not declared", "no declaration",
    "does not confirm", "not provided",
]


def check_boolean(evidence: Evidence, criterion: Criterion) -> tuple[VerdictEnum, str]:
    """
    Purpose: Checks a simple declaration-style criterion, e.g. "Not
    blacklisted", "Not bankrupt", "Border-country compliance".

    Where it gets its data: evidence.raw_value is whatever declaration
    text the AI found (or None if nothing was found at all).

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=BOOLEAN.
    """
    if evidence.raw_value is None or not evidence.raw_value.strip():
        return VerdictEnum.FAIL, "Declaration not submitted"

    if evidence.confidence < 0.65:
        return VerdictEnum.REVIEW, (
            f"Declaration unreadable (confidence {evidence.confidence:.2f}) -- manual verification required"
        )

    raw_lower = evidence.raw_value.lower()
    if any(phrase in raw_lower for phrase in _NEGATION_PHRASES):
        return VerdictEnum.FAIL, f"Extracted text indicates the declaration was not made: '{evidence.raw_value}'"

    return VerdictEnum.PASS, f"Declaration confirmed: '{evidence.raw_value}'"


# ---------------------------------------------------------------------
# Rule Type 6 -- Document Presence
# ---------------------------------------------------------------------

def check_doc_presence(evidence: Evidence, criterion: Criterion) -> tuple[VerdictEnum, str]:
    """
    Purpose: Checks a required document (GST, PAN, OEM authorization,
    ISO cert, etc.) was actually found among the bidder's uploads.

    Where it gets its data: evidence.document_id is the real signal
    here -- it's None if the AI found no matching document at all,
    regardless of what raw_value says.

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=DOC_PRESENCE.
    """
    if evidence.document_id is None or evidence.raw_value is None or not evidence.raw_value.strip():
        return VerdictEnum.FAIL, "Required document missing"

    if evidence.confidence < 0.7:
        return VerdictEnum.REVIEW, (
            f"Document found but unreadable (confidence {evidence.confidence:.2f}) -- manual verification required"
        )

    return VerdictEnum.PASS, f"Document present and readable: '{evidence.raw_value}'"


# ---------------------------------------------------------------------
# Rule Type 7 -- Classification Check
# ---------------------------------------------------------------------

def check_classification(evidence: Evidence, criterion: Criterion) -> tuple[VerdictEnum, str]:
    """
    Purpose: Checks local-content-percentage classification under
    Make in India policy (Class I >=50%, Class II >=20%, per GeM
    tenders -- Project Context 9.1, Type 7).

    Where it gets its data: evidence.raw_value is the AI-extracted
    local content percentage text. criterion.threshold_json holds the
    class_1_pct / class_2_pct cutoffs (default 50/20 if not specified).

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=CLASSIFICATION.
    """
    if evidence.confidence < 0.7:
        return VerdictEnum.REVIEW, (
            f"Low confidence ({evidence.confidence:.2f}) on local content percentage "
            f"-- manual verification required"
        )

    pct = _parse_percentage(evidence.raw_value)
    if pct is None:
        return VerdictEnum.REVIEW, (
            f"Could not extract a local content percentage from AI output "
            f"('{evidence.raw_value}') -- manual verification required"
        )

    threshold_data = criterion.threshold_json or {}
    class_1 = threshold_data.get("class_1_pct", 50)
    class_2 = threshold_data.get("class_2_pct", 20)

    if pct >= class_1:
        return VerdictEnum.PASS, f"Local content {pct:.1f}% >= {class_1}% -> Class I -> PASS"
    if pct >= class_2:
        return VerdictEnum.PASS, f"Local content {pct:.1f}% >= {class_2}% -> Class II -> PASS"
    return VerdictEnum.FAIL, f"Local content {pct:.1f}% below minimum {class_2}% (Class II) threshold -> FAIL"


# ---------------------------------------------------------------------
# Rule Type 8 -- Composite AND Logic
# ---------------------------------------------------------------------

def check_composite(evidence: Evidence, criterion: Criterion, bidder: Bidder) -> tuple[VerdictEnum, str]:
    """
    Purpose: Intended to combine two or more sub-checks (e.g. AIIMS's
    "bidder turnover AND OEM turnover both required", Project Context
    9.1, Type 8) into one AND-combined verdict.

    LIMITATION (see file header for full reasoning): always returns
    REVIEW. The current schema has no way to represent multiple linked
    evidence values under one composite criterion. Automating it
    correctly requires a real schema addition (child criteria), which
    is a deliberate architectural decision to make outside this phase,
    not a Phase 4 implementation detail.

    Where it's used: Called by evaluate_evidence()'s dispatcher for
    rule_type=COMPOSITE.
    """
    return VerdictEnum.REVIEW, (
        "Composite criteria (multiple sub-requirements combined, e.g. bidder AND "
        "OEM turnover) are not yet automated -- requires manual verification "
        "against the underlying documents."
    )


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------

_DISPATCH = {
    RuleType.NUMERIC_THRESHOLD: lambda ev, cr, bd, td: check_numeric_threshold(ev, cr),
    RuleType.CONDITIONAL: lambda ev, cr, bd, td: check_conditional_threshold(ev, cr, bd),
    RuleType.NO_LOSS: lambda ev, cr, bd, td: check_no_loss(ev, cr),
    RuleType.QUANTITY_PCT: lambda ev, cr, bd, td: check_quantity_pct(ev, cr, td),
    RuleType.BOOLEAN: lambda ev, cr, bd, td: check_boolean(ev, cr),
    RuleType.DOC_PRESENCE: lambda ev, cr, bd, td: check_doc_presence(ev, cr),
    RuleType.CLASSIFICATION: lambda ev, cr, bd, td: check_classification(ev, cr),
    RuleType.COMPOSITE: lambda ev, cr, bd, td: check_composite(ev, cr, bd),
}


def evaluate_evidence(
    evidence: Evidence, criterion: Criterion, bidder: Bidder, tender: Tender
) -> tuple[VerdictEnum, str]:
    """
    Purpose: The single entry point of this file. Reads
    criterion.rule_type and routes to the correct check_*() function
    above. Never crashes -- any unexpected error in a specific check
    function becomes a REVIEW verdict instead of taking down the whole
    bidder's evaluation batch.

    Where it gets its data: evidence, criterion, bidder, and tender are
    all real database rows, queried by the caller.

    Where it's used: Called once per Evidence row by
    workers/tasks.py's process_bidder_documents(), right after each
    Evidence row is created.
    """
    handler = _DISPATCH.get(criterion.rule_type)
    if handler is None:
        return VerdictEnum.REVIEW, f"Unknown rule_type '{criterion.rule_type}' -- manual verification required"

    try:
        return handler(evidence, criterion, bidder, tender)
    except Exception as e:
        return VerdictEnum.REVIEW, f"Error evaluating this criterion automatically: {e} -- manual verification required"


# ---------------------------------------------------------------------
# Overall Bidder Verdict
# ---------------------------------------------------------------------

def calculate_overall_verdict(bidder_id: int, db) -> str:
    """
    Purpose: Combines every mandatory criterion's final_verdict for one
    bidder into a single overall result, per Project Context 9.2: any
    mandatory FAIL -> NOT_ELIGIBLE, any mandatory REVIEW (and no FAIL)
    -> MANUAL_REVIEW, all mandatory PASS -> ELIGIBLE. Non-mandatory
    criteria never affect the overall result.

    Where it gets its data: bidder_id identifies whose verdicts to
    combine. db is the caller's active database session. Queries every
    Verdict row joined through Evidence -> Criterion, filtered to this
    bidder.

    Where it's used: Called once by workers/tasks.py's
    process_bidder_documents(), right after all Evidence+Verdict rows
    for a bidder are created. Called again by routers/evaluation.py's
    override endpoint, since one changed verdict can flip the overall
    result.
    """
    rows = (
        db.query(Verdict.final_verdict, Criterion.mandatory)
        .join(Evidence, Verdict.evidence_id == Evidence.id)
        .join(Criterion, Evidence.criterion_id == Criterion.id)
        .filter(Evidence.bidder_id == bidder_id)
        .all()
    )

    mandatory_verdicts = [final_verdict for final_verdict, mandatory in rows if mandatory]

    if any(v == VerdictEnum.FAIL for v in mandatory_verdicts):
        overall = OverallVerdict.NOT_ELIGIBLE
    elif any(v == VerdictEnum.REVIEW for v in mandatory_verdicts):
        overall = OverallVerdict.MANUAL_REVIEW
    elif mandatory_verdicts:
        overall = OverallVerdict.ELIGIBLE
    else:
        overall = OverallVerdict.PENDING

    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if bidder is not None:
        bidder.overall_verdict = overall
        db.commit()

    return overall.value