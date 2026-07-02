"""
backend/app/routers/bidders.py
---------------------------------
Purpose: A bidder applies to a specific tender (creates a Bidder row),
and evaluators/auditors view who has applied. Document upload for bids
is added in Phase 2.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.bidder import Bidder
from app.schemas.bidder import BidderCreate, BidderResponse

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