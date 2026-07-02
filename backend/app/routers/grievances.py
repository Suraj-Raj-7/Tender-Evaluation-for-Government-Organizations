"""
backend/app/routers/grievances.py
------------------------------------
Purpose: Lets a bidder raise a grievance after losing an evaluation, and
lets auditors/bidders view grievances. Per spec 5.8, this only logs the
complaint -- it never reopens evaluation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.bidder import Bidder
from app.models.tender import Tender, TenderStatus
from app.models.grievance import Grievance
from app.schemas.grievance import GrievanceCreate, GrievanceResponse

router = APIRouter(prefix="/grievances", tags=["grievances"])


@router.post("", response_model=GrievanceResponse)
def submit_grievance(
    tender_id: int,
    request: GrievanceCreate,
    current_user: User = Depends(require_role(RoleEnum.BIDDER.value)),
    db: Session = Depends(get_db),
):
    """
    Records a bidder's objection. tender_id passed as a query param.
    Only allowed once the tender's evaluation is officially closed
    (per spec 5.8 -- grievances happen after the fact, not during).
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")
    if tender.status != TenderStatus.TECHNICAL_COMPLETE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grievances can only be raised after evaluation is complete",
        )

    bidder = db.query(Bidder).filter(
        Bidder.tender_id == tender_id, Bidder.user_id == current_user.id
    ).first()
    if bidder is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You did not apply to this tender")

    grievance = Grievance(bidder_id=bidder.id, tender_id=tender_id, description=request.description)
    db.add(grievance)
    db.commit()
    db.refresh(grievance)
    return grievance


@router.get("", response_model=list[GrievanceResponse])
def list_grievances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Auditors see every grievance platform-wide. Bidders see only their own."""
    if current_user.role == RoleEnum.AUDITOR:
        return db.query(Grievance).all()

    if current_user.role == RoleEnum.BIDDER:
        bidder_ids = [b.id for b in db.query(Bidder).filter(Bidder.user_id == current_user.id).all()]
        return db.query(Grievance).filter(Grievance.bidder_id.in_(bidder_ids)).all()

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to view grievances")