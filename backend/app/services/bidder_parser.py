"""
backend/app/services/bidder_parser.py
------------------------------------------
Purpose: Given a bidder's combined document text and a tender's already
-extracted list of criteria, finds and extracts the specific evidence
value for each criterion. This is the "matching" counterpart to
tender_parser.py's "discovery" -- criteria already exist here; we're
just locating proof of each one inside a bidder's paperwork.

Why this file exists: Evidence rows (models/evidence.py) need a
specific value, confidence score, and rationale per (bidder, criterion)
pair. This file is the one place that builds the prompt asking the AI
to find that evidence, and safely parses the result -- exactly like
tender_parser.py does for criteria, but matching against known targets
instead of discovering unknowns.
"""

import json

from app.services.llm import call_llm


# The instructions sent to the AI. {criteria_list} and {bidder_text}
# are filled in per bidder, per tender, each time extract_evidence()
# runs.
_EVIDENCE_PROMPT_TEMPLATE = """You are reviewing a bidder's submitted documents against a government tender's eligibility criteria.

Below is a list of criteria that must be checked. For EACH criterion, search the bidder's document text and find the specific value or proof that addresses it.

Criteria to check:
{criteria_list}

Respond with a JSON object of exactly this shape:
{{"evidence": [ <one object per criterion, in the same order given above> ]}}

Each evidence object must have exactly these fields:
- "criterion_id": the exact id number of the criterion this evidence is for (copy it from the list above)
- "raw_value": the specific value/text found in the documents that addresses this criterion, or null if nothing relevant was found at all
- "confidence": your confidence this extraction is correct, as a number from 0.0 to 1.0 (use a LOW value like 0.3 or below if the text is unclear, ambiguous, or you are guessing -- never guess high confidence)
- "ai_rationale": a short explanation of why you extracted this value and where in the text you found it
- "page_number": a page number if the text clearly indicates one, or null if not identifiable

Bidder's document text:
{bidder_text}
"""


def _format_criteria_for_prompt(criteria: list[dict]) -> str:
    """
    Purpose: Turns a list of Criterion data into a readable, numbered
    block of text the AI can check the bidder's documents against.

    Where it gets its data: criteria is a list of dicts, each
    representing one row from the Criterion table for this tender
    (id, code, description, evidence_hint) -- passed in by whichever
    Celery task calls extract_evidence() below.

    Where it's used: Called once by extract_evidence(), to build the
    "Criteria to check" section of the prompt above.
    """
    lines = []
    for criterion in criteria:
        hint = criterion.get("evidence_hint")
        hint_text = f" (look for: {hint})" if hint else ""
        lines.append(
            f"- id={criterion['id']} [{criterion['code']}]: "
            f"{criterion['description']}{hint_text}"
        )
    return "\n".join(lines)


def _validate_evidence_dict(item: dict, index: int, valid_criterion_ids: set[int]) -> None:
    """
    Purpose: Checks that one parsed evidence object has the fields the
    Evidence database model requires, that its criterion_id actually
    matches one of the criteria we asked about, and that confidence is
    a real number between 0.0 and 1.0 -- catching a malformed AI
    response here, with a clear error, instead of it crashing later
    inside a database insert.

    Where it gets its data: item is one element from the "evidence"
    array inside the AI's parsed JSON response. valid_criterion_ids is
    the set of criterion ids we actually asked about, built by
    extract_evidence() below.

    Where it's used: Called once per evidence item by extract_evidence()
    below, right after parsing the AI's JSON response.

    Raises: ValueError with a specific, readable reason if validation
    fails -- the calling Celery task will catch this and mark the Job
    as FAILED with this exact message.
    """
    required_fields = ["criterion_id", "raw_value", "confidence", "ai_rationale"]
    for field in required_fields:
        if field not in item:
            raise ValueError(f"Evidence at index {index} is missing required field '{field}'")

    if item["criterion_id"] not in valid_criterion_ids:
        raise ValueError(
            f"Evidence at index {index} references criterion_id "
            f"{item['criterion_id']}, which was not in the list of criteria asked about"
        )

    confidence = item["confidence"]
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValueError(
            f"Evidence at index {index} has invalid confidence '{confidence}' "
            f"-- must be a number between 0.0 and 1.0"
        )


def extract_evidence(bidder_text: str, criteria: list[dict]) -> list[dict]:
    """
    Purpose: The main entry point of this file. Takes a bidder's full
    combined document text and the tender's existing criteria, and
    returns a list of validated evidence dictionaries -- one per
    criterion -- ready to be turned into Evidence database rows.

    Where it gets its data: bidder_text comes from combining every
    Document row's extracted_text for one bidder (filled in by
    services/ocr.py in Phase 2). criteria comes from querying the
    Criterion table for this tender (each dict needs at least "id",
    "code", "description", and optionally "evidence_hint").

    Where it's used: Will be called by workers/tasks.py's
    process_bidder_documents task, right after downloading and OCR'ing
    all of one bidder's uploaded documents.

    Note: This function returns evidence with NO verdict attached --
    it only reports what it found and how confident it is. Deciding
    PASS/FAIL/REVIEW from this evidence is the rules engine's job
    (Phase 4), never this file's.

    Raises: ValueError if the AI's response isn't valid JSON, doesn't
    contain an "evidence" list, or contains an item referencing an
    unknown criterion / missing required fields / invalid confidence.
    """
    valid_criterion_ids = {c["id"] for c in criteria}

    prompt = _EVIDENCE_PROMPT_TEMPLATE.format(
        criteria_list=_format_criteria_for_prompt(criteria),
        bidder_text=bidder_text,
    )

    raw_response = call_llm(prompt, json_mode=True)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"AI response was not valid JSON: {e}\nRaw response was:\n{raw_response}"
        )

    if not isinstance(parsed, dict) or "evidence" not in parsed:
        raise ValueError(
            f"AI response was valid JSON but missing an 'evidence' key. Got: {parsed}"
        )

    evidence_list = parsed["evidence"]
    if not isinstance(evidence_list, list):
        raise ValueError(
            f"'evidence' was present but not a list. Got: {type(evidence_list)}"
        )

    for index, item in enumerate(evidence_list):
        _validate_evidence_dict(item, index, valid_criterion_ids)

    return evidence_list