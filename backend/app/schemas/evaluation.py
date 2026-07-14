"""
backend/app/schemas/evaluation.py
-------------------------------------
Purpose: JSON shapes for the Evaluation Matrix and Evidence Detail
views -- the core screens an Evaluator uses to review AI verdicts and
override them. Built in Phase 4, consumed by the frontend in Phase 5.
"""

from datetime import datetime
from pydantic import BaseModel
from app.models.criterion import CriterionCategory
from app.models.bidder import BidderCategory, OverallVerdict
from app.models.verdict import VerdictEnum


class MatrixCriterion(BaseModel):
    """One column header in the evaluation matrix. Used by: GET /tenders/{id}/matrix."""
    id: int
    code: str
    description: str
    category: CriterionCategory
    mandatory: bool


class MatrixCell(BaseModel):
    """
    One cell in the evaluation matrix grid -- the evidence + verdict for
    one (bidder, criterion) pair. Used by: GET /tenders/{id}/matrix,
    nested inside each MatrixBidder.evidence dict, keyed by criterion code.
    """
    evidence_id: int
    raw_value: str | None
    confidence: float
    ai_verdict: VerdictEnum
    final_verdict: VerdictEnum
    is_overridden: bool
    ai_rationale: str | None
    document_id: int | None
    page_number: int | None
    doc_name: str | None


class MatrixBidder(BaseModel):
    """
    One row in the evaluation matrix -- one bidder's overall result plus
    their evidence for every criterion. Used by: GET /tenders/{id}/matrix.
    """
    id: int
    company_name: str
    category: BidderCategory
    overall_verdict: OverallVerdict
    evidence: dict[str, MatrixCell]


class MatrixResponse(BaseModel):
    """
    Full evaluation matrix for one tender -- powers the entire
    EvaluationMatrix page (Phase 5) from a single API call.
    Used by: GET /tenders/{id}/matrix.
    """
    criteria: list[MatrixCriterion]
    bidders: list[MatrixBidder]


class OverrideHistoryItem(BaseModel):
    """
    One past override, shown in the Evidence Panel's history section.
    Used by: GET /evidence/{id}, nested inside EvidenceDetailResponse.
    """
    id: int
    officer_id: int
    from_verdict: VerdictEnum
    to_verdict: VerdictEnum
    reason: str
    overridden_at: datetime

    model_config = {"from_attributes": True}


class EvidenceDetailResponse(BaseModel):
    """
    Full detail for one evidence cell, shown when an Evaluator clicks a
    matrix cell to open the Evidence Panel. Used by: GET /evidence/{id}.
    """
    evidence_id: int
    criterion_code: str
    criterion_description: str
    raw_value: str | None
    confidence: float
    ai_rationale: str | None
    document_id: int | None
    doc_name: str | None
    page_number: int | None
    extracted_at: datetime
    verdict_id: int
    ai_verdict: VerdictEnum
    final_verdict: VerdictEnum
    is_overridden: bool
    override_history: list[OverrideHistoryItem]