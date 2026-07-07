"""
backend/app/services/tender_parser.py
------------------------------------------
Purpose: Converts a tender's raw extracted document text into a list
of structured criterion dictionaries, ready to be saved as Criterion
rows. This is where "AI extraction" actually becomes usable data.

Why this file exists: call_llm() (services/llm.py) only returns plain
text -- it has no idea what a "criterion" is. This file is the one
place that knows the exact shape the Criterion table needs, builds a
prompt asking the AI for exactly that shape, and safely parses
whatever text comes back into real Python dictionaries.

Note: The AI is asked for a JSON OBJECT ({"criteria": [...]}) rather
than a bare JSON array. This is required because Groq's JSON mode
(enabled via call_llm's json_mode flag) only guarantees valid syntax
for objects, not bare arrays -- wrapping it costs nothing and keeps
the same prompt working identically across every provider.
"""

import json

from app.services.llm import call_llm
from app.models.criterion import CriterionCategory, RuleType


# Every allowed value, pulled directly from the same enums the database
# uses (models/criterion.py) -- so this file can never drift out of
# sync with what the Criterion table actually accepts.
_ALLOWED_CATEGORIES = [c.value for c in CriterionCategory]
_ALLOWED_RULE_TYPES = [r.value for r in RuleType]


# The instructions sent to the AI. Written once, reused for every
# tender. {tender_text} is filled in with the specific document's
# extracted text each time extract_criteria() runs.
_EXTRACTION_PROMPT_TEMPLATE = """You are analyzing an Indian government tender document (NIT) to extract eligibility criteria that bidders must satisfy.

Read the tender text below and identify every distinct eligibility criterion (financial thresholds, experience requirements, registrations, certifications, declarations, etc).

Respond with a JSON object of exactly this shape:
{{"criteria": [ <one object per criterion> ]}}

Each criterion object must have exactly these fields:
- "code": a short identifier like "C1", "C2", "C3" (sequential, starting from C1)
- "category": one of {categories}
- "description": the full requirement text, in your own words if needed, but complete and legally precise
- "rule_type": one of {rule_types}
- "operator": a comparison operator if relevant (e.g. ">=", "<="), or null if not applicable
- "threshold_json": an object holding whatever numeric/structured data this rule needs (e.g. {{"value": 50, "unit": "Lakhs", "years": 3}}), or null if not applicable
- "mandatory": true if failing this criterion disqualifies the bidder, false if it's just noted
- "evidence_hint": a short hint about which document would prove this (e.g. "CA certificate", "GST registration"), or null
- "msme_exempt": true only if the tender text explicitly exempts MSME/Startup companies from this specific criterion, otherwise false

Tender text:
{tender_text}
"""


def _validate_criterion_dict(item: dict, index: int) -> None:
    """
    Purpose: Checks that one parsed criterion object actually has the
    fields the Criterion database model requires, and that its
    category/rule_type values are ones the database enum actually
    accepts -- catching a malformed AI response here, with a clear
    error, instead of it crashing later inside a database insert.

    Where it gets its data: item is one element from the "criteria"
    array inside the AI's parsed JSON response.

    Where it's used: Called once per criterion by extract_criteria()
    below, right after parsing the AI's JSON response.

    Raises: ValueError with a specific, readable reason if validation
    fails -- the caller (a Celery task) will catch this and mark the
    Job as FAILED with this exact message.
    """
    required_fields = ["code", "category", "description", "rule_type", "mandatory"]
    for field in required_fields:
        if field not in item:
            raise ValueError(f"Criterion at index {index} is missing required field '{field}'")

    if item["category"] not in _ALLOWED_CATEGORIES:
        raise ValueError(
            f"Criterion at index {index} has invalid category '{item['category']}'. "
            f"Must be one of {_ALLOWED_CATEGORIES}"
        )

    if item["rule_type"] not in _ALLOWED_RULE_TYPES:
        raise ValueError(
            f"Criterion at index {index} has invalid rule_type '{item['rule_type']}'. "
            f"Must be one of {_ALLOWED_RULE_TYPES}"
        )


def extract_criteria(tender_text: str) -> list[dict]:
    """
    Purpose: The main entry point of this file. Takes a tender's full
    extracted document text and returns a list of validated criterion
    dictionaries, ready to be turned into Criterion database rows.

    Where it gets its data: tender_text comes from a Document row's
    extracted_text column (filled in by services/ocr.py during Phase 2,
    for the tender's NIT document specifically).

    Where it's used: Will be called by workers/tasks.py's
    process_tender_document task, right after downloading and OCR'ing
    a newly uploaded NIT document.

    Raises: ValueError if the AI's response isn't valid JSON, doesn't
    contain a "criteria" list, or contains a criterion missing required
    fields / using an invalid category or rule_type. The calling Celery
    task is responsible for catching this and marking the Job as
    FAILED with the error message -- this function never silently
    returns bad data.
    """
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        categories=_ALLOWED_CATEGORIES,
        rule_types=_ALLOWED_RULE_TYPES,
        tender_text=tender_text,
    )

    # json_mode=True makes the provider itself guarantee valid JSON
    # syntax -- this is what prevents the mismatched-quote corruption
    # seen in earlier testing.
    raw_response = call_llm(prompt, json_mode=True)

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"AI response was not valid JSON: {e}\nRaw response was:\n{raw_response}"
        )

    if not isinstance(parsed, dict) or "criteria" not in parsed:
        raise ValueError(
            f"AI response was valid JSON but missing a 'criteria' key. Got: {parsed}"
        )

    criteria_list = parsed["criteria"]
    if not isinstance(criteria_list, list):
        raise ValueError(
            f"'criteria' was present but not a list. Got: {type(criteria_list)}"
        )

    for index, item in enumerate(criteria_list):
        _validate_criterion_dict(item, index)

    return criteria_list