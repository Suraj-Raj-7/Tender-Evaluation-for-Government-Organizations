# app/services/rules.py

def check_turnover(extracted_val_str, threshold, bidder_category):
    """
    Validates Financial Turnover with MSME exemptions.
    """
    try:
        # Clean string like '145.5 Lakhs' to float 145.5
        val = float(''.join(c for c in extracted_val_str if c.isdigit() or c == '.'))
    except ValueError:
        return "REVIEW", "Could not parse numeric value for turnover."

    # MSME Exemption logic from GFR 2017
    if bidder_category.upper() in ["MSME", "STARTUP"]:
        return "PASS", f"Exempted under GFR 2017 rules for {bidder_category}."
    
    if val >= threshold:
        return "PASS", f"Value {val}L satisfies the {threshold}L threshold."
    return "FAIL", f"Value {val}L is below the required {threshold}L."

def check_80_60_40(projects, tender_value):
    """
    Calculates project experience logic:
    - 1 work of 80% value
    - 2 works of 60% value
    - 3 works of 40% value
    """
    if not projects:
        return "FAIL", "No technical project evidence found."

    p80 = [p for p in projects if p.get('value', 0) >= tender_value * 0.8]
    p60 = [p for p in projects if p.get('value', 0) >= tender_value * 0.6]
    p40 = [p for p in projects if p.get('value', 0) >= tender_value * 0.4]
    
    if len(p80) >= 1: 
        return "PASS", f"Satisfies criteria: Found 1 work (Value: {p80[0]['value']}L) >= 80%."
    if len(p60) >= 2: 
        return "PASS", f"Satisfies criteria: Found 2 works >= 60%."
    if len(p40) >= 3: 
        return "PASS", f"Satisfies criteria: Found 3 works >= 40%."
    
    return "REVIEW", "Project volume combination does not meet 80/60/40 thresholds."

