# app/routers/criteria.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.models import Tender, Criterion, Document
from app.services.tender_parser import extract_criteria

router = APIRouter(prefix="/tenders/{tender_id}/criteria", tags=["Criteria"])

@router.post("/extract")
def trigger_extraction(tender_id: int, db: SASession = Depends(get_db)):
    t = db.get(Tender, tender_id)
    doc = db.query(Document).filter_by(tender_id=tender_id, bidder_id=None).first()
         
    if not doc or not doc.extracted_text:
        raise HTTPException(400, "No readable tender document found. Ensure OCR is working.")
             
    proposed_criteria = extract_criteria(doc.extracted_text)
         
    for c in proposed_criteria:
        # Matches the keys returned by your SCHEMA_HINT in tender_parser.py
        db.add(Criterion(
            tender_id=tender_id, 
            code=c['code'], 
            category=c['category'],
            description=c['description'], 
            evidence_type=c.get('evidence_type', 'GENERAL'),
            operator=c['operator'],
            threshold_json={"value": c['threshold']}, # Storing as JSON to match your model[cite: 4]
            mandatory=c['mandatory']
        ))
    db.commit()
    return {"status": "success", "count": len(proposed_criteria)}