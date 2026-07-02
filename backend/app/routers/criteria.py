"""
backend/app/routers/criteria.py
----------------------------------
Purpose: View, manually add, edit, and delete a tender's eligibility
criteria. AI auto-extraction of criteria is built in Phase 3 -- this
file only handles manual CRUD for now.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User, RoleEnum
from app.models.criterion import Criterion
from app.schemas.criterion import CriterionResponse, CriterionCreate, CriterionEdit

router = APIRouter(tags=["criteria"])


@router.get("/tenders/{tender_id}/criteria", response_model=list[CriterionResponse])
def list_criteria(
    tender_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all criteria for one tender. Open to any logged-in role, since
    bidders also need to read criteria before applying."""
    return db.query(Criterion).filter(Criterion.tender_id == tender_id).all()


@router.post("/criteria", response_model=CriterionResponse)
def create_criterion(
    tender_id: int,
    request: CriterionCreate,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """Manually adds a criterion the AI missed. tender_id passed as a query param."""
    criterion = Criterion(tender_id=tender_id, **request.model_dump())
    db.add(criterion)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.patch("/criteria/{criterion_id}", response_model=CriterionResponse)
def edit_criterion(
    criterion_id: int,
    request: CriterionEdit,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """Partially updates a criterion -- only fields the Publisher actually
    changed are sent (all fields optional in CriterionEdit)."""
    criterion = db.query(Criterion).filter(Criterion.id == criterion_id).first()
    if criterion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Criterion not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(criterion, field, value)

    db.commit()
    db.refresh(criterion)
    return criterion


@router.delete("/criteria/{criterion_id}")
def delete_criterion(
    criterion_id: int,
    current_user: User = Depends(require_role(RoleEnum.PUBLISHER.value)),
    db: Session = Depends(get_db),
):
    """Removes a criterion the Publisher decides shouldn't apply."""
    criterion = db.query(Criterion).filter(Criterion.id == criterion_id).first()
    if criterion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Criterion not found")

    db.delete(criterion)
    db.commit()
    return {"message": "Criterion deleted"}