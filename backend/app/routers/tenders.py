"""
backend/app/routers/tenders.py
---------------------------------
Purpose: Create/view tenders, change status, assign evaluators, issue
corrigenda. NIT document upload is added in Phase 2 (needs OCR/storage,
not built yet).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.tender import Tender, TenderEvaluator
from app.models.criterion import Criterion
from app.models.corrigendum import Corrigendum
from app.schemas.tender import (
    TenderCreate, TenderResponse, TenderStatusUpdate,
    TenderEvaluatorAssign, CorrigendumCreate, CorrigendumResponse,
)

router = APIRouter(prefix="/tenders", tags=["tenders"])


def _to_response(tender: Tender, db: Session) -> TenderResponse:
    """
    Purpose: Builds a TenderResponse including criteria_count, which
    isn't a real database column -- it's counted here from the criteria
    table. Where it's used: every endpoint below that returns tender data.
    """
    count = db.query(Criterion).filter(Criterion.tender_id == tender.id).count()
    return TenderResponse(
        id=tender.id, name=tender.name, status=tender.status,
        estimated_value=tender.estimated_value, deadline=tender.deadline,
        created_at=tender.created_at, criteria_count=count,
    )


@router.post("", response_model=TenderResponse)
def create_tender(
    request: TenderCreate,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """Creates a new tender in DRAFT status. Data from Publisher's Create Tender form."""
    tender = Tender(
        created_by=current_user.id, name=request.name, description=request.description,
        estimated_value=request.estimated_value, deadline=request.deadline,
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)
    return _to_response(tender, db)


@router.get("", response_model=list[TenderResponse])
def list_tenders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists tenders, filtered by role: Evaluators see only tenders assigned
    to them (via TenderEvaluator). Everyone else sees all tenders.
    """
    if current_user.role == RoleEnum.EVALUATOR:
        assigned_ids = [
            te.tender_id for te in
            db.query(TenderEvaluator).filter(TenderEvaluator.user_id == current_user.id).all()
        ]
        tenders = db.query(Tender).filter(Tender.id.in_(assigned_ids)).all()
    else:
        tenders = db.query(Tender).all()
    return [_to_response(t, db) for t in tenders]


@router.get("/{tender_id}", response_model=TenderResponse)
def get_tender(
    tender_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns one tender's details. tender_id comes from the URL path."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return _to_response(tender, db)


@router.patch("/{tender_id}/status", response_model=TenderResponse)
def update_tender_status(
    tender_id: int,
    request: TenderStatusUpdate,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """Changes a tender's lifecycle status, e.g. DRAFT -> PUBLISHED."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")
    tender.status = request.status
    db.commit()
    db.refresh(tender)
    return _to_response(tender, db)


@router.post("/{tender_id}/evaluators")
def assign_evaluator(
    tender_id: int,
    request: TenderEvaluatorAssign,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """
    Assigns an Evaluator to a tender (junction row). request.user_id
    must belong to a user with role=EVALUATOR.
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    evaluator = db.query(User).filter(User.id == request.user_id).first()
    if evaluator is None or evaluator.role != RoleEnum.EVALUATOR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not an evaluator")

    existing = db.query(TenderEvaluator).filter(
        TenderEvaluator.tender_id == tender_id, TenderEvaluator.user_id == request.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already assigned")

    db.add(TenderEvaluator(tender_id=tender_id, user_id=request.user_id))
    db.commit()
    return {"message": "Evaluator assigned successfully"}


@router.post("/{tender_id}/corrigendum", response_model=CorrigendumResponse)
def issue_corrigendum(
    tender_id: int,
    request: CorrigendumCreate,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """
    Issues an amendment. If is_material, extends the tender's deadline
    and moves status to CORRIGENDUM_ISSUED (per spec 5.5).
    """
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender not found")

    corrigendum = Corrigendum(
        tender_id=tender_id, issued_by=current_user.id,
        description=request.description, is_material=request.is_material,
        new_deadline=request.new_deadline,
    )
    db.add(corrigendum)

    if request.is_material and request.new_deadline:
        tender.deadline = request.new_deadline
        tender.status = tender.status.__class__.CORRIGENDUM_ISSUED

    db.commit()
    db.refresh(corrigendum)
    return corrigendum


@router.get("/{tender_id}/corrigenda", response_model=list[CorrigendumResponse])
def list_corrigenda(
    tender_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists every amendment ever issued for a tender, newest actions included."""
    return db.query(Corrigendum).filter(Corrigendum.tender_id == tender_id).all()