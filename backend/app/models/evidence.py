"""
backend/app/models/evidence.py
---------------------------------
Purpose: Defines the Evidence table -- one row per (bidder, criterion)
pair, holding exactly what the AI extraction pipeline found for that
criterion from that bidder's documents.

Why this file exists: This table is intentionally immutable -- once a
row is created, no code anywhere should ever call db.commit() after
modifying one. This guarantees a permanent, unaltered record of what
the AI originally found, which is what makes the platform legally
defensible for CAG audits and RTI requests.
"""

from datetime import datetime, timezone
from sqlalchemy import Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Evidence(Base):
    """
    Purpose: One row per (bidder, criterion) combination -- the AI's raw
    finding: what value it extracted, how confident it was, why it
    believes this value is correct, and which document/page it came from.

    Where it's used: Created once by bidder_parser.py during Phase 3's AI
    extraction. Read (never written again) by the rules engine (Phase 4)
    and displayed in the Evidence Panel (Phase 5).

    IMPORTANT: No route or service should ever UPDATE a row in this table
    after it's created. If a value needs correcting, that's what the
    separate Verdict/Override tables (next file) are for.
    """
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    bidder_id: Mapped[int] = mapped_column(ForeignKey("bidders.id"), nullable=False)

    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"), nullable=False)

    # Which uploaded file this value was found in. Nullable because some
    # criteria may have no matching document found at all.
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    # The actual value the AI extracted, e.g. "184 Lakhs" or "GSTIN: 27ABCDE1234F1Z5".
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI's confidence in this extraction, 0.0 to 1.0. Low confidence drives
    # the rules engine's "REVIEW, never FAIL" safety behavior.
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # AI's explanation of why it extracted this value, e.g.
    # "Found turnover figure in CA certificate, page 3, FY 2023-24."
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )