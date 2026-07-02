"""
backend/app/schemas/tender.py
--------------------------------
Purpose: JSON shapes for creating tenders, assigning evaluators, and
issuing corrigenda (amendments).
"""

from datetime import datetime
from pydantic import BaseModel
from app.models.tender import TenderStatus


class TenderCreate(BaseModel):
    """Shape to create a new tender. Used by: POST /tenders (Publisher)."""
    name: str
    description: str
    estimated_value: float
    deadline: datetime


class TenderResponse(BaseModel):
    """Tender data returned to frontend. Used by: GET /tenders, GET /tenders/{id}."""
    id: int
    name: str
    status: TenderStatus
    estimated_value: float
    deadline: datetime
    created_at: datetime
    criteria_count: int

    model_config = {"from_attributes": True}


class TenderStatusUpdate(BaseModel):
    """Shape to change a tender's status. Used by: PATCH /tenders/{id}/status."""
    status: TenderStatus


class TenderEvaluatorAssign(BaseModel):
    """Shape to assign an evaluator to a tender. Used by: POST /tenders/{id}/evaluators."""
    user_id: int


class CorrigendumCreate(BaseModel):
    """Shape to issue an amendment. Used by: POST /tenders/{id}/corrigendum."""
    description: str
    is_material: bool
    new_deadline: datetime | None = None


class CorrigendumResponse(BaseModel):
    """Corrigendum data returned to frontend. Used by: GET /tenders/{id}/corrigenda."""
    id: int
    description: str
    is_material: bool
    new_deadline: datetime | None
    issued_at: datetime

    model_config = {"from_attributes": True}