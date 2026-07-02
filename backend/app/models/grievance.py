"""
backend/app/models/grievance.py
----------------------------------
Purpose: Defines the Grievance table -- one row per complaint a bidder
raises after losing, questioning their evaluation result.

Why this file exists: GFR 2017 legally requires a mechanism for
unsuccessful bidders to object. This table logs the objection only --
it never reopens evaluation or allows new document uploads.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import Integer, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GrievanceStatus(str, enum.Enum):
    """
    Purpose: Tracks where a grievance is in the review process.
    Where it's used: Grievance.status column below. Only an Auditor
    updates this (in later phases).
    """
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"


class Grievance(Base):
    """
    Purpose: One row per bidder complaint about their evaluation result.

    Where it's used: routers/grievances.py's POST /grievances endpoint
    (Bidder only, after evaluation is TECHNICAL_COMPLETE) creates these.
    Auditors view and resolve them via routers/audit.py in later phases.
    """
    __tablename__ = "grievances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    bidder_id: Mapped[int] = mapped_column(ForeignKey("bidders.id"), nullable=False)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[GrievanceStatus] = mapped_column(
        Enum(GrievanceStatus), default=GrievanceStatus.SUBMITTED, nullable=False
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)