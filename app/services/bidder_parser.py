import json
from app.services.llm import extract_json


def extract_all_evidence(combined_text: str, criteria_list: list, ocr_confidence: float):
    # Shorten text to avoid the 'Tokens Per Minute' limit
    safe_text = combined_text[:12000]
    
    criteria_descriptions = "\n".join([f"- {c.code}: {c.description}" for c in criteria_list])  
    prompt = f"""
    You are an expert auditor. Based on the following criteria discovered in the tender:
    {criteria_descriptions}

    Extract evidence from the bidder's documents (OCR Quality: {ocr_confidence}).
    
    ### FOR EACH CRITERION FOUND IN THE LIST ABOVE, EXTRACT:
    - 'code': The matching code (e.g., C1).
    - 'val': The numeric/text value found.
    - 'issued_date': Date of issue or 'NA'.
    - 'expiry_date': Expiry date or 'NA'.
    - 'doc_name': Filename where found.
    - 'conf': Confidence (0.0 to 1.0).
    - 'reason': Short rationale.

    ### BIDDER TEXT:
    {combined_text[:9000]}

    ### OUTPUT FORMAT (STRICT JSON ARRAY):
    [
      {{"code": "C1", "val": "145L", "issued_date": "2024-03-01", "expiry_date": "NA", "doc_name": "Audit.pdf", "conf": 0.95, "reason": "Turnover confirmed from CA cert."}}
    ]
    """
    return extract_json(prompt, criteria_list)