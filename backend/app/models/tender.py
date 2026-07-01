"""
backend/app/models/tender.py
------------------------------
Purpose: Defines the Tender table (one row per government tender created
by a Publisher) and the TenderEvaluator table (which Evaluators are
assigned to which Tenders -- a many-to-many link).

Why this file exists: The Tender is the central object the whole platform
revolves around. Every Criterion, Bidder, and Evidence row will point
back to a Tender via tender_id.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TenderStatus(str, enum.Enum):
    """
    Purpose: The fixed lifecycle stages a tender moves through, in order.
    Stored as text in the database.

    Where it's used: Tender.status column below. Routers check and update
    this as officers create, publish, and evaluate tenders.
    """
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CORRIGENDUM_ISSUED = "CORRIGENDUM_ISSUED"
    EVALUATION = "EVALUATION"
    TECHNICAL_COMPLETE = "TECHNICAL_COMPLETE"
    NO_QUALIFIED_BIDDERS = "NO_QUALIFIED_BIDDERS"
    AWARDED = "AWARDED"
    CANCELLED = "CANCELLED"


class Tender(Base):
    """
    Purpose: One row per government tender. Holds its basic details and
    current lifecycle status.

    Where it's used: routers/tenders.py creates and updates these.
    Criterion, Bidder, Document, and Corrigendum rows all reference a
    Tender via tender_id (added when we build those files).
    """
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Which Publisher created this tender.
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(300), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Stored in Lakhs, per the project's Indian government context.
    estimated_value: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus), default=TenderStatus.DRAFT, nullable=False
    )

    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TenderEvaluator(Base):
    """
    Purpose: Junction table -- one row means "this User (an Evaluator) is
    assigned to this Tender." Lets one tender have many evaluators, and
    one evaluator be assigned to many tenders.

    Where it's used: routers/tenders.py's assign-evaluator endpoint creates
    these rows. routers/evaluation.py checks this table to confirm an
    evaluator is allowed to see a given tender's matrix.
    """
    __tablename__ = "tender_evaluators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )