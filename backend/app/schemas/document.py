"""
backend/app/schemas/document.py
-----------------------------------
Purpose: JSON shapes for document upload responses and document listing.
"""

from datetime import datetime
from pydantic import BaseModel


class UploadResponse(BaseModel):
    """
    Purpose: Shape returned immediately after any file upload -- the
    frontend uses job_id to start polling for processing status.
    Where it's used: Returned by NIT upload and bidder document upload endpoints.
    """
    document_id: int | None = None
    job_id: str


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