"""
backend/app/routers/grievances.py
------------------------------------
Purpose: Lets a bidder raise a grievance after losing an evaluation, and
lets auditors/bidders view grievances. Per spec 5.8, this only logs the
complaint -- it never reopens evaluation.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.bidder import Bidder
from app.models.tender import Tender, TenderStatus
from app.models.grievance import Grievance
from app.schemas.grievance import GrievanceCreate, GrievanceResponse, GrievanceDetailResponse
from app.services.audit_logger import log_action

router = APIRouter(prefix="/grievances", tags=["grievances"])


@router.post("", response_model=GrievanceResponse)
def submit_grievance(
    tender_id: int,
    request: GrievanceCreate,
    http_request: Request,
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
    db.flush()  # assigns grievance.id, needed for the log entry below

    log_action(
        db,
        user_id=current_user.id,
        action="GRIEVANCE_SUBMITTED",
        entity_type="grievance",
        entity_id=grievance.id,
        new_value={"tender_id": tender_id, "bidder_id": bidder.id},
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()
    db.refresh(grievance)
    return grievance


@router.get("", response_model=list[GrievanceResponse])
def list_grievances(
    tender_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Auditors see every grievance platform-wide (optionally filtered to
    one tender). Bidders see only their own (optionally filtered to
    one tender too).

    Where it gets its data: tender_id is an optional query param, e.g.
    GET /grievances?tender_id=1 -- omit it to see all of the caller's
    visible grievances across every tender.
    """
    if current_user.role == RoleEnum.AUDITOR:
        query = db.query(Grievance)
        if tender_id is not None:
            query = query.filter(Grievance.tender_id == tender_id)
        return query.all()

    if current_user.role == RoleEnum.BIDDER:
        bidder_ids = [b.id for b in db.query(Bidder).filter(Bidder.user_id == current_user.id).all()]
        query = db.query(Grievance).filter(Grievance.bidder_id.in_(bidder_ids))
        if tender_id is not None:
            query = query.filter(Grievance.tender_id == tender_id)
        return query.all()

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to view grievances")


@router.get("/{grievance_id}", response_model=GrievanceDetailResponse)
def get_grievance_detail(
    grievance_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Purpose: Full detail for one grievance. Auditors can view any
    grievance; a bidder can only view their own.

    Where it gets its data: grievance_id from the URL. Access is
    checked against the grievance's own bidder_id for the BIDDER role.

    Where it's used: will be called by a future grievance detail page
    -- not currently linked from any existing frontend page, since
    BidderPortal.jsx's grievance flow (built later in this phase) only
    needs the list/submit endpoints, not this one. Provided now to
    close the gap against the full spec.
    """
    grievance = db.query(Grievance).filter(Grievance.id == grievance_id).first()
    if grievance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance not found")

    if current_user.role == RoleEnum.BIDDER:
        bidder = db.query(Bidder).filter(
            Bidder.id == grievance.bidder_id, Bidder.user_id == current_user.id
        ).first()
        if bidder is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your grievance")
    elif current_user.role != RoleEnum.AUDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to view this grievance")

    return grievance