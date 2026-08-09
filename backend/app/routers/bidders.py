"""
backend/app/routers/bidders.py
---------------------------------
Purpose: A bidder applies to a specific tender (creates a Bidder row),
evaluators/auditors view who has applied, a bidder views their own
applications across all tenders, and bidders upload their supporting
documents (with the hard deadline lock enforced).
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
from app.schemas.bidder import BidderCreate, BidderResponse, MyApplicationResponse
from app.schemas.document import BidderUploadResponse
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
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    if datetime.now(timezone.utc) > tender.deadline:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bid submission deadline has passed. No further applications can be accepted.",
        )

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


@router.get("/bidders/me", response_model=list[MyApplicationResponse])
def list_my_applications(
    current_user: User = Depends(require_role(RoleEnum.BIDDER.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Lists every tender the logged-in bidder has applied to,
    combined with that tender's name/status/deadline, in one call.

    Where it gets its data: every Bidder row where user_id matches the
    logged-in bidder, joined in Python with each row's parent Tender
    (kept simple/explicit rather than a SQL join, since a bidder
    realistically has few applications).

    Where it's used: called once by BidderPortal.jsx (Phase 5) to
    render the bidder's "My Applications" list.
    """
    bidder_rows = db.query(Bidder).filter(Bidder.user_id == current_user.id).all()

    results = []
    for bidder in bidder_rows:
        tender = db.query(Tender).filter(Tender.id == bidder.tender_id).first()
        if tender is None:
            continue
        results.append(MyApplicationResponse(
            id=bidder.id,
            tender_id=tender.id,
            tender_name=tender.name,
            tender_status=tender.status,
            tender_deadline=tender.deadline,
            company_name=bidder.company_name,
            category=bidder.category,
            overall_verdict=bidder.overall_verdict,
            applied_at=bidder.applied_at,
        ))
    return results


@router.post("/tenders/{tender_id}/bidders/{bidder_id}/documents", response_model=BidderUploadResponse)
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

    Note: no OCR or AI processing happens here anymore -- documents
    are just saved. Evidence extraction is deferred until the
    Evaluator begins the tender's evaluation (see
    routers/evaluation.py's begin_evaluation endpoint), after the
    deadline has passed and every bidder's final document set is known.
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

    document_ids = []
    for upload in files:
        contents = await upload.read()
        storage_path = upload_file(contents, upload.filename, upload.content_type)
        document = Document(
            tender_id=tender_id,
            bidder_id=bidder_id,
            uploaded_by=current_user.id,
            storage_path=storage_path,
            original_filename=upload.filename,
            mime_type=upload.content_type,
        )
        db.add(document)
        db.flush()  # assigns document.id
        document_ids.append(document.id)

    db.commit()

    return BidderUploadResponse(document_ids=document_ids)