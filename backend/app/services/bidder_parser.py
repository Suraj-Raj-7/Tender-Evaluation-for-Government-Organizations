"""
backend/app/services/bidder_parser.py
------------------------------------------
Purpose: Given a bidder's documents (each with its own extracted text)
and a tender's already-extracted list of criteria, finds and extracts
the specific evidence value for each criterion, including which
document it came from. This is the "matching" counterpart to
tender_parser.py's "discovery" -- criteria already exist here; we're
just locating proof of each one inside a bidder's paperwork.

Why this file exists: Evidence rows (models/evidence.py) need a
specific value, confidence score, rationale, and source document per
(bidder, criterion) pair -- required for the Evidence Panel's "source
document, exact page" display (project spec 2.4). This file builds the
prompt asking the AI to find that evidence per-document, and safely
parses the result.
"""


import json

from app.services.llm import call_llm


_EVIDENCE_PROMPT_TEMPLATE = """You are reviewing a bidder's submitted documents against a government tender's eligibility criteria.

Below is a list of criteria that must be checked. For EACH criterion, search the bidder's documents below and find the specific value or proof that addresses it.

Criteria to check:
{criteria_list}

Bidder's documents (each tagged with its document_id):
{documents_text}

Respond with a JSON object of exactly this shape:
{{"evidence": [ <one object per criterion, in the same order given above> ]}}

Each evidence object must have exactly these fields:
- "criterion_id": the exact id number of the criterion this evidence is for (copy it from the list above)
- "document_id": the exact document_id (from the tags above) where you found this evidence, or null if nothing relevant was found in any document
- "raw_value": the specific value/text found that addresses this criterion, or null if nothing relevant was found at all
- "confidence": your confidence this extraction is correct, as a number from 0.0 to 1.0 (use a LOW value like 0.3 or below if the text is unclear, ambiguous, or you are guessing -- never guess high confidence)
- "ai_rationale": a short explanation of why you extracted this value and which document it came from
- "page_number": a page number if the text clearly indicates one, or null if not identifiable
"""


def _format_criteria_for_prompt(criteria: list[dict]) -> str:
    """
    Purpose: Turns a list of Criterion data into a readable, numbered
    block of text the AI can check the bidder's documents against.

    Where it gets its data: criteria is a list of dicts (id, code,
    description, evidence_hint) -- one per row from the Criterion
    table for this tender, passed in by whichever Celery task calls
    extract_evidence() below.

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


# Spec-mandated safety cap: prevents a bidder with many/large documents
# from producing a prompt so large it blows past provider context
# limits or becomes needlessly expensive to run.
_MAX_COMBINED_TEXT_CHARS = 12000


def _format_documents_for_prompt(documents: list[dict]) -> str:
    """
    Purpose: Turns a list of a bidder's documents into a clearly
    tagged block of text, so the AI can report exactly which document
    each piece of evidence came from. Truncates the combined result if
    it exceeds a safe size limit.

    Where it gets its data: documents is a list of dicts, each with
    "id" (the Document row's database id) and "text" (that document's
    OCR/extracted text) -- passed in by extract_evidence() below.

    Where it's used: Called once by extract_evidence(), to build the
    "Bidder's documents" section of the prompt above.
    """
    parts = []
    for doc in documents:
        parts.append(f"--- document_id={doc['id']} ---\n{doc['text']}")
    combined = "\n\n".join(parts)

    if len(combined) > _MAX_COMBINED_TEXT_CHARS:
        combined = combined[:_MAX_COMBINED_TEXT_CHARS] + "\n\n[TRUNCATED -- remaining document text omitted]"

    return combined


def _validate_evidence_dict(item: dict, index: int, valid_criterion_ids: set[int], valid_document_ids: set[int]) -> None:
    """
    Purpose: Checks that one parsed evidence object has the fields the
    Evidence database model requires, that its criterion_id and
    document_id (if given) actually match ones we asked about, and
    that confidence is a real number between 0.0 and 1.0.

    Where it gets its data: item is one element from the "evidence"
    array inside the AI's parsed JSON response. valid_criterion_ids
    and valid_document_ids are built by extract_evidence() below.

    Where it's used: Called once per evidence item by extract_evidence()
    below, right after parsing the AI's JSON response.

    Raises: ValueError with a specific, readable reason if validation
    fails -- the calling Celery task will catch this and mark the Job
    as FAILED with this exact message.
    """
    required_fields = ["criterion_id", "document_id", "raw_value", "confidence", "ai_rationale"]
    for field in required_fields:
        if field not in item:
            raise ValueError(f"Evidence at index {index} is missing required field '{field}'")

    if item["criterion_id"] not in valid_criterion_ids:
        raise ValueError(
            f"Evidence at index {index} references unknown criterion_id {item['criterion_id']}"
        )

    if item["document_id"] is not None and item["document_id"] not in valid_document_ids:
        raise ValueError(
            f"Evidence at index {index} references unknown document_id {item['document_id']}"
        )

    confidence = item["confidence"]
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValueError(
            f"Evidence at index {index} has invalid confidence '{confidence}' "
            f"-- must be a number between 0.0 and 1.0"
        )


def extract_evidence(documents: list[dict], criteria: list[dict]) -> list[dict]:
    """
    Purpose: The main entry point of this file. Takes a bidder's
    documents (each with its own text) and the tender's existing
    criteria, and returns a list of validated evidence dictionaries --
    one per criterion -- ready to be turned into Evidence database rows.

    Where it gets its data: documents is built by the calling Celery
    task from every Document row belonging to one bidder, after OCR
    has filled in each row's extracted_text (services/ocr.py, Phase 2).
    criteria comes from querying the Criterion table for this tender.

    Where it's used: Called by workers/tasks.py's
    process_bidder_documents task, right after OCR'ing all of one
    bidder's uploaded documents.

    Note: This function returns evidence with NO verdict attached --
    it only reports what it found, how confident it is, and which
    document it came from. Deciding PASS/FAIL/REVIEW from this
    evidence is the rules engine's job (Phase 4), never this file's.

    Raises: ValueError if the AI's response isn't valid JSON, doesn't
    contain an "evidence" list, or contains an item referencing an
    unknown criterion/document, missing required fields, or invalid
    confidence.
    """
    valid_criterion_ids = {c["id"] for c in criteria}
    valid_document_ids = {d["id"] for d in documents}

    prompt = _EVIDENCE_PROMPT_TEMPLATE.format(
        criteria_list=_format_criteria_for_prompt(criteria),
        documents_text=_format_documents_for_prompt(documents),
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
        raise ValueError(f"'evidence' was present but not a list. Got: {type(evidence_list)}")

    for index, item in enumerate(evidence_list):
        _validate_evidence_dict(item, index, valid_criterion_ids, valid_document_ids)

    return evidence_list