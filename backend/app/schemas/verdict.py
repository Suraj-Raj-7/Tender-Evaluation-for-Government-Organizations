"""
backend/app/schemas/verdict.py
---------------------------------
Purpose: Defines the JSON shapes for viewing a verdict and submitting
an override.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from app.models.verdict import VerdictEnum


class VerdictResponse(BaseModel):
    """
    Purpose: Shape of verdict data shown in the evaluation matrix and
    evidence panel.
    Where it's used: Returned as part of GET /tenders/{id}/matrix and
    GET /evidence/{id}.
    """
    id: int
    ai_verdict: VerdictEnum
    final_verdict: VerdictEnum
    is_overridden: bool
    decided_at: datetime

    model_config = {"from_attributes": True}


class OverrideRequest(BaseModel):
    """
    Purpose: Shape of an override submission. reason has a minimum
    length of 10 characters -- enforced here so a bad request is
    rejected before it ever reaches the database.
    Where it's used: POST /verdicts/{id}/override request body
    (Evaluator only).
    """
    to_verdict: VerdictEnum
    reason: str = Field(min_length=10)