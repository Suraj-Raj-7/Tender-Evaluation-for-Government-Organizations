"""
backend/app/models/document.py
---------------------------------
Purpose: Defines the Document table -- one row per uploaded file, whether
it's a tender's NIT document (uploaded by a Publisher) or a bidder's
supporting document (uploaded by a Bidder). Stores where the file lives
in MinIO and what text was extracted from it.

Why this file exists: OCR results (Phase 2) and AI extraction (Phase 3)
both write into this table's extracted_text and ocr_confidence columns.
Evidence rows (built later) point back to a Document to show "this value
came from this file, on this page."
"""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Document(Base):
    """
    Purpose: One row per uploaded file. bidder_id is null for a tender's
    NIT document, and set for a bidder's submitted document.

    Where it's used: routers/tenders.py (NIT upload) and routers/bidders.py
    (bid document upload) create these rows in Phase 2. services/ocr.py
    fills in extracted_text, ocr_confidence, is_scanned, page_count after
    processing.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    # Null for a tender's own NIT document. Set for a bidder's submission.
    bidder_id: Mapped[int | None] = mapped_column(ForeignKey("bidders.id"), nullable=True)

    # Who actually clicked upload -- a Publisher for NIT, a Bidder for their docs.
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Where the actual file bytes live in MinIO (set in Phase 2's storage.py).
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)

    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # True if this was a scanned image/PDF (needed Tesseract), False if it
    # was a digital PDF (pdfplumber could read it directly).
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 1.0 for digital PDFs. Lower for OCR'd scans -- used by the rules
    # engine's "low confidence -> REVIEW, never FAIL" safety rule.
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Full text pulled out by pdfplumber/Tesseract. Filled in by Phase 2/3.
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )