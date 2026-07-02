"""
backend/app/models/corrigendum.py
------------------------------------
Purpose: Defines the Corrigendum table -- one row per amendment issued
to a published tender (e.g. deadline extension, criteria clarification).

Why this file exists: Per GFR 2017, amendments to a live tender must be
tracked and published on the same channel as the original. is_material
determines whether bidders get to resubmit documents (deadline changes)
or it's just a notice (clarification only).
"""

from datetime import datetime, timezone
from sqlalchemy import Integer, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Corrigendum(Base):
    """
    Purpose: One row per amendment to a tender.

    Where it's used: routers/tenders.py's corrigendum endpoint (Publisher
    only) creates these. If is_material is True, the tender's deadline
    is extended and bidders can re-upload documents.
    """
    __tablename__ = "corrigenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    issued_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # True = criteria or deadline changed (bidders get resubmission window).
    # False = clarification only (just a notice, no resubmission).
    is_material: Mapped[bool] = mapped_column(Boolean, nullable=False)

    new_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )