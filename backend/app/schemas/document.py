"""
backend/app/schemas/document.py
-----------------------------------
Purpose: JSON shapes for document upload responses and document listing.
"""

from datetime import datetime
from pydantic import BaseModel


class UploadResponse(BaseModel):
    """
    Purpose: Shape returned immediately after a tender's NIT document
    upload -- the frontend uses job_id to start polling for criteria
    extraction status. NIT documents still process immediately
    (unlike bidder documents, see BidderUploadResponse below).
    Where it's used: Returned by the NIT upload endpoint.
    """
    document_id: int | None = None
    job_id: str


class BidderUploadResponse(BaseModel):
    """
    Purpose: Shape returned after a bidder uploads documents. No
    processing job is created here -- AI evidence extraction is
    deliberately deferred until the Evaluator begins evaluation after
    the deadline passes (see routers/evaluation.py's begin_evaluation
    endpoint). Returns the saved document IDs so the frontend can
    immediately refresh its "already uploaded" list.
    Where it's used: Returned by the bidder document upload endpoint.
    """
    document_ids: list[int]


class DocumentResponse(BaseModel):
    """
    Purpose: Metadata about one uploaded document (not the file bytes
    themselves -- those are served separately via GET /documents/{id}).
    Where it's used: Returned by GET /bidders/{id}/documents.
    """
    id: int
    original_filename: str
    mime_type: str
    is_scanned: bool
    ocr_confidence: float
    page_count: int | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}