# app/routers/tenders.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app import models 
from app.storage import storage
from app.audit import log
# Ensure both functions are imported here
from app.services.extract_text import extract_from_path, process_files
from app.services import tender_parser, bidder_parser

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.get("/{tender_id}/document")
def get_tender_document(tender_id: int, db: SASession = Depends(get_db)):
    """Allows bidders and evaluators to view the original tender PDF"""
    doc = db.query(models.Document).filter_by(tender_id=tender_id, bidder_id=None).first()
    if not doc:
        raise HTTPException(status_code=404, detail="NIT Document not found")
    
    return FileResponse(
        doc.storage_path, 
        media_type="application/pdf", 
        filename=doc.original_filename
    )

@router.get("/")
def list_tenders(db: SASession = Depends(get_db)):
    return db.query(models.Tender).all()

@router.post("")
async def create_tender(
    name: str = Form(...),
    estimated_value: float = Form(0.0),
    tender_doc: UploadFile = File(None),
    db: SASession = Depends(get_db)
):
    """Creates a tender and DYNAMICALLY extracts criteria using AI"""
    t = models.Tender(name=name, estimated_value=estimated_value, status="PUBLISHED")
    db.add(t)
    db.commit()
    db.refresh(t)
         
    if tender_doc and tender_doc.filename:
        path, size = storage.save(tender_doc.filename, tender_doc.file)
        text, conf, pages, scanned = extract_from_path(path)
        
        # --- NEW: AI CRITERIA DISCOVERY BLOCK ---
        # This calls the new function that scans for Financial/Experience/Tax rules
        discovered_criteria = tender_parser.extract_criteria(text)
        
        for crit in discovered_criteria:
            new_crit = models.Criterion(
                tender_id=t.id,
                code=crit['code'],
                category=crit['category'],
                description=crit['description'],
                operator=crit.get('operator', '>='),
                threshold_json=crit.get('threshold_json', {}),
                mandatory=crit.get('mandatory', True)
            )
            db.add(new_crit)
        # ----------------------------------------

        d = models.Document(
            tender_id=t.id, 
            original_filename=tender_doc.filename,
            storage_path=path, 
            mime_type=tender_doc.content_type or "",
            is_scanned=scanned, 
            page_count=pages, 
            extracted_text=text,
            ocr_confidence=conf, 
            uploaded_by_id=1 
        )
        db.add(d)
        db.commit()
         
        log(db, "admin", "TENDER_CREATED", {"tender_id": t.id, "criteria_found": len(discovered_criteria)})
    
    return RedirectResponse(url="/", status_code=303)

@router.post("/{tender_id}/bidders/{bidder_id}/upload")
async def upload_bidder_docs(
    tender_id: int, 
    bidder_id: int, 
    files: list[UploadFile], 
    db: SASession = Depends(get_db)
):
    # 1. Process files first to get combined text
    combined_text, avg_conf = process_files(files) 
    
    # 2. Fetch the 7+ criteria you discovered during tender creation
    db_criteria = db.query(models.Criterion).filter_by(tender_id=tender_id).all()
    if not db_criteria:
        raise HTTPException(status_code=400, detail="Criteria list missing in database.")

    # 3. Call AI - If it worked before with these 4 docs, it will work now.
    try:
        evidence_data = bidder_parser.extract_all_evidence(combined_text, db_criteria, avg_conf)
    except Exception as e:
        raise HTTPException(status_code=429, detail=str(e))

    # 4. TRANSACTION: Ensure everything is saved together or nothing is.
    try:
        # Remove any partial old data to avoid duplicates
        db.query(models.Evidence).filter_by(bidder_id=bidder_id).delete()

        for ev in evidence_data:
            # Map the AI response EXACTLY to your DB columns
            new_ev = models.Evidence(
                bidder_id=bidder_id,
                criterion_code=ev['code'],
                raw_value=str(ev['val']),
                confidence=ev.get('conf', 0.9),
                rationale=ev.get('reason', 'Extracted from document'),
                issued_date=ev.get('issued_date', 'NA'),
                expiry_date=ev.get('expiry_date', 'NA'),
                doc_refs={"primary_doc": ev.get('doc_name', 'Verified Document')}
            )
            db.add(new_ev)
        
        # Update the Bidder status to trigger the frontend matrix
        bidder = db.query(models.Bidder).filter_by(id=bidder_id).first()
        if bidder:
            bidder.overall_verdict = "UNDER_REVIEW"
            db.add(bidder)
        
        db.commit() # Save everything to app.db
        return {"status": "Success", "mapped_criteria": len(evidence_data)}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database save failed.")