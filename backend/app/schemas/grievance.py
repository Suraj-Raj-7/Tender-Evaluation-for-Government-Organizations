"""
backend/app/schemas/grievance.py
-----------------------------------
Purpose: Defines the JSON shapes for a bidder submitting a grievance
and viewing grievance status.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from app.models.grievance import GrievanceStatus


class GrievanceCreate(BaseModel):
    """
    Purpose: Shape of a grievance submission. description has a minimum
    length of 20 characters, so a bidder can't submit a one-word complaint
    with no real explanation.
    Where it's used: POST /grievances request body (Bidder only).
    """
    description: str = Field(min_length=20)


class GrievanceResponse(BaseModel):
    """
    Purpose: Shape of grievance data returned to bidders and auditors
    in list views.
    Where it's used: Returned by GET /grievances.
    """
    id: int
    status: GrievanceStatus
    submitted_at: datetime
    description: str

    model_config = {"from_attributes": True}


class GrievanceDetailResponse(BaseModel):
    """
    Purpose: Fuller shape of one grievance, including which tender and
    bidder it belongs to and any resolution notes -- more than the
    list view needs, but exactly what a single-grievance detail page
    should show.
    Where it's used: Returned by GET /grievances/{id}.
    """
    id: int
    tender_id: int
    bidder_id: int
    status: GrievanceStatus
    description: str
    submitted_at: datetime
    resolved_at: datetime | None
    resolution_notes: str | None

    model_config = {"from_attributes": True}