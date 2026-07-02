"""
backend/app/schemas/criterion.py
-----------------------------------
Purpose: Defines the JSON shapes for viewing, manually adding, and
editing tender eligibility criteria.
"""

from pydantic import BaseModel
from app.models.criterion import CriterionCategory, RuleType


class CriterionResponse(BaseModel):
    """
    Purpose: Full shape of one criterion, as shown to Publishers reviewing
    AI-extracted criteria and Evaluators viewing the matrix.
    Where it's used: Returned by GET /tenders/{id}/criteria.
    """
    id: int
    tender_id: int
    code: str
    category: CriterionCategory
    description: str
    rule_type: RuleType
    operator: str | None
    threshold_json: dict | None
    mandatory: bool
    evidence_hint: str | None
    msme_exempt: bool

    model_config = {"from_attributes": True}


class CriterionCreate(BaseModel):
    """
    Purpose: Shape of data for a Publisher manually adding a criterion
    the AI missed.
    Where it's used: POST /criteria request body (Publisher only).
    """
    code: str
    category: CriterionCategory
    description: str
    rule_type: RuleType
    operator: str | None = None
    threshold_json: dict | None = None
    mandatory: bool = True
    evidence_hint: str | None = None
    msme_exempt: bool = False


class CriterionEdit(BaseModel):
    """
    Purpose: Shape of a partial update to an existing criterion -- every
    field optional, so a Publisher can fix just one wrong field without
    resending the whole criterion.
    Where it's used: PATCH /criteria/{id} request body (Publisher only).
    """
    code: str | None = None
    category: CriterionCategory | None = None
    description: str | None = None
    rule_type: RuleType | None = None
    operator: str | None = None
    threshold_json: dict | None = None
    mandatory: bool | None = None
    evidence_hint: str | None = None
    msme_exempt: bool | None = None