import json
from app.services.llm import extract_json

def extract_criteria(tender_text: str):
    prompt = f"""
    You are a professional procurement analyst. Analyze the following Tender Document and extract ALL eligibility criteria.
    
    ### CATEGORIES TO LOOK FOR:
    1. Financial: Turnover (3yr avg), Net Worth, Solvency, Profit/Loss history.
    2. Experience: Similar work (80/60/40 rules), completion certificates, specific technical specs.
    3. Statutory: PAN, GSTIN, EPFO, ESIC, MSME status.
    4. Legal: Entity type, Incorporation age, Blacklisting/Debarment status.

    ### INSTRUCTIONS:
    - Assign a unique code like 'C1', 'C2', 'C3'... to each.
    - For 'threshold_json', include the numeric target (e.g., {{"value": 100, "unit": "Lakhs"}}).
    - Identify the 'operator' (e.g., '>=', '==', 'NOT_IN').

    ### TENDER TEXT:
    {tender_text[:10000]}

    ### OUTPUT FORMAT (JSON ARRAY):
    [
      {{
        "code": "C1",
        "category": "Financial Turnover",
        "description": "Average annual turnover of last 3 years must be >= 50% of tender value",
        "operator": ">=",
        "threshold_json": {{"value_percentage": 50, "years": 3}},
        "mandatory": true
      }}
    ]
    """
    return extract_json(prompt)