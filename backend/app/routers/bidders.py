"""
backend/app/routers/bidders.py
---------------------------------
Purpose: A bidder applies to a specific tender (creates a Bidder row),
evaluators/auditors view who has applied, and bidders upload their
supporting documents (with the hard deadline lock enforced).
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.tender import Tender
from app.models.bidder import Bidder
from app.models.document import Document
from app.models.job import Job, JobType, JobStatus
from app.schemas.bidder import BidderCreate, BidderResponse
from app.schemas.document import UploadResponse
from app.services.storage import upload_file

router = APIRouter(tags=["bidders"])


@router.post("/tenders/{tender_id}/bidders", response_model=BidderResponse)
def apply_to_tender(
    tender_id: int,
    request: BidderCreate,
    current_user: User = Depends(require_role(RoleEnum.BIDDER.value)),
    db: Session = Depends(get_db),
):
    """
    Creates a Bidder row linking the logged-in bidder's account to this
    tender. Falls back to the bidder's saved company_name/gstin (from
    registration) if not provided in the request.
    """
    existing = db.query(Bidder).filter(
        Bidder.tender_id == tender_id, Bidder.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already applied to this tender")

    bidder = Bidder(
        tender_id=tender_id,
        user_id=current_user.id,
        company_name=request.company_name or current_user.company_name,
        gstin=request.gstin or current_user.gstin,
        cin=request.cin,
        category=request.category,
    )
    db.add(bidder)
    db.commit()
    db.refresh(bidder)
    return bidder


@router.get("/tenders/{tender_id}/bidders", response_model=list[BidderResponse])
def list_bidders_for_tender(
    tender_id: int,
    current_user: User = Depends(require_role(RoleEnum.EVALUATOR.value, RoleEnum.AUDITOR.value)),
    db: Session = Depends(get_db),
):
    """Lists every bidder who applied to a tender. Only Evaluators/Auditors
    can see the full bidder list -- bidders never see each other (spec 2.3)."""
    return db.query(Bidder).filter(Bidder.tender_id == tender_id).all()


@router.post("/tenders/{tender_id}/bidders/{bidder_id}/documents", response_model=UploadResponse)
async def upload_bid_documents(
    tender_id: int,
    bidder_id: int,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role(RoleEnum.BIDDER.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Uploads one or more supporting documents for a bidder's
    application. HARD DEADLINE LOCK: rejected immediately if the
    tender's deadline has already passed (legal requirement, spec 5.2).

    Where it gets its data: files are whatever the bidder selects in
    their application form -- multiple files in one request. tender_id
    and bidder_id come from the URL path.

    Where it's used: Called from the BidderPortal page (Phase 5) before
    the deadline passes.

    Note: Real OCR + evidence extraction happens in Phase 3's Celery
    worker. This just stores the files and creates one PENDING Job.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    if datetime.now(timezone.utc) > tender.deadline:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bid submission deadline has passed. No further documents can be accepted.",
        )

    bidder = db.query(Bidder).filter(
        Bidder.id == bidder_id, Bidder.user_id == current_user.id
    ).first()
    if bidder is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your application")

    for upload in files:
        contents = await upload.read()
        storage_path = upload_file(contents, upload.filename, upload.content_type)
        db.add(Document(
            tender_id=tender_id,
            bidder_id=bidder_id,
            uploaded_by=current_user.id,
            storage_path=storage_path,
            original_filename=upload.filename,
            mime_type=upload.content_type,
        ))

    job = Job(
        tender_id=tender_id, bidder_id=bidder_id,
        type=JobType.BIDDER_EXTRACTION, status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return UploadResponse(job_id=job.id)