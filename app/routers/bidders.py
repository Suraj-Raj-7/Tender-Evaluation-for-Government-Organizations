from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.models import Bidder, Document, Evidence
from app.storage import storage
from app.services.extract_text import extract_from_path
from app.services.bidder_parser import extract_all_evidence

# Ensure prefix matches what the frontend calls
router = APIRouter(prefix="/tenders/{tender_id}/bidders", tags=["Bidders"])
@router.post("/{bidder_id}/upload")
async def upload_bidder_docs(tender_id: int, bidder_id: int, files: list[UploadFile] = File(...), db: SASession = Depends(get_db)):
    """Handles multi-file uploads with database integrity fixes."""
    
    # Ensure Bidder exists
    bidder = db.query(Bidder).filter_by(id=bidder_id).first()
    if not bidder:
        bidder = Bidder(id=bidder_id, tender_id=tender_id, name=f"Bidder {bidder_id}", category="GENERAL")
        db.add(bidder)
        db.commit()
        db.refresh(bidder)

    combined_text = ""
    avg_conf = 0
    
    for f in files:
        # Save and Extract
        path, size = storage.save(f.filename, f.file)
        text, conf, pages, scanned = extract_from_path(path)
        
        # FIX: Ensure mime_type is never None to satisfy database constraints
        mtype = f.content_type if f.content_type else "application/pdf"
        
        # Save Document Record with all required fields
        d = Document(
            tender_id=tender_id, 
            bidder_id=bidder_id, 
            original_filename=f.filename,
            storage_path=path, 
            extracted_text=text, 
            ocr_confidence=conf, 
            mime_type=mtype,      # Fixed: Added explicit value
            is_scanned=scanned,   # Fixed: Added from OCR result
            page_count=pages,     # Fixed: Added from OCR result
            uploaded_by_id=1
        )
        db.add(d)
        combined_text += f"\n--- {f.filename} ---\n{text}"
        avg_conf = (avg_conf + conf) / 2 if avg_conf > 0 else conf

    # Run AI Evidence Mapping
    evidence_items = extract_all_evidence(combined_text, avg_conf)
    
    # Clean old evidence
    db.query(Evidence).filter_by(bidder_id=bidder_id).delete()

    for ev in evidence_items:
        new_ev = Evidence(
            bidder_id=bidder_id, 
            criterion_code=ev['code'],
            raw_value=ev['val'], 
            confidence=ev['conf'],
            rationale=ev['reason'], 
            doc_refs={"source": "Upload Bundle"}
        )
        db.add(new_ev)

    db.commit()
    return {"status": "success", "message": "Documents processed by AI."}