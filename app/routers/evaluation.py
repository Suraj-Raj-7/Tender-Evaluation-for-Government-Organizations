from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.models import Bidder, Evidence, Criterion, Tender
from app.services.rules import check_turnover

router = APIRouter()

@router.get("/{tender_id}/matrix_full")
def get_matrix_data(tender_id: int, db: SASession = Depends(get_db)):
    tender = db.query(Tender).filter_by(id=tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    bidders = db.query(Bidder).filter_by(tender_id=tender_id).all()
    # Fetch real criteria from the database linked to this tender
    db_criteria = db.query(Criterion).filter_by(tender_id=tender_id).all()
    
    # Format criteria for the frontend table headers
    formatted_criteria = [
        {"code": c.code, "description": c.category, "full_text": c.description} 
        for c in db_criteria
    ]
    
    if not formatted_criteria:
        # Fallback only if no criteria exist in DB
        formatted_criteria = [{"code": "C1", "description": "Turnover"}, {"code": "C2", "description": "Experience"}]

    matrix_results = []
    for b in bidders:
        evidence_list = db.query(Evidence).filter_by(bidder_id=b.id).all()
        evidence_map = {e.criterion_code: {
            "val": e.raw_value, 
            "conf": e.confidence, 
            "rationale": e.rationale,
            "issued": e.issued_date or "NA",
            "expiry": e.expiry_date or "NA",
            "doc_name": e.doc_refs.get("primary_doc") if e.doc_refs else "Unknown Document"
        } for e in evidence_list}
        
        # LOGIC FIX: Determine overall verdict based on evidence
        # If any mandatory criterion is missing or low confidence (< 0.8), set to REVIEW
        verdict = "ELIGIBLE"
        for c in db_criteria:
            ev = evidence_map.get(c.code)
            if not ev:
                verdict = "INCOMPLETE"
                break
            if ev["conf"] < 0.8:
                verdict = "REVIEW" # Cannot be PASS if AI is unsure
        
        matrix_results.append({
            "id": b.id, 
            "name": b.name, 
            "category": b.category,
            "verdict": verdict, 
            "evidence": evidence_map
        })
        
    return {"bidders": matrix_results, "criteria": formatted_criteria}