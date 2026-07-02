"""
backend/app/models/bidder.py
-------------------------------
Purpose: Defines the Bidder table -- one row per company that has applied
to a specific tender. Holds company details relevant to eligibility
checks (category, age) and tracks their overall evaluation result.

Why this file exists: Every Document, Evidence, and Verdict row a bidder
submits will link back to a Bidder row via bidder_id. This is the anchor
for everything the rules engine (Phase 4) evaluates.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BidderCategory(str, enum.Enum):
    """
    Purpose: Some criteria give exemptions to MSME/Startup companies
    (per GFR 2017). This category drives that exemption logic.
    Where it's used: Bidder.category column below, checked by the rules
    engine's check_conditional_threshold() in Phase 4.
    """
    GENERAL = "GENERAL"
    MSME = "MSME"
    STARTUP = "STARTUP"


class OverallVerdict(str, enum.Enum):
    """
    Purpose: The bidder's final result after all their criteria are
    evaluated together.
    Where it's used: Bidder.overall_verdict column below. Set by
    calculate_overall_verdict() in Phase 4's rules engine.
    """
    PENDING = "PENDING"
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Bidder(Base):
    """
    Purpose: One row per company's application to one specific tender.
    (The same company applying to 3 tenders creates 3 separate Bidder rows.)

    Where it's used: routers/bidders.py creates these on application.
    Document, Evidence rows link here via bidder_id. The Evaluation
    Matrix (Phase 4/5) uses this as one row of the grid.
    """
    __tablename__ = "bidders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    # Nullable: a bidder's login account may not exist yet at the moment
    # this row is created (e.g. bulk-registered by an officer).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    company_name: Mapped[str] = mapped_column(String(300), nullable=False)

    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)

    cin: Mapped[str | None] = mapped_column(String(30), nullable=True)

    category: Mapped[BidderCategory] = mapped_column(
        Enum(BidderCategory), default=BidderCategory.GENERAL, nullable=False
    )

    # Used by CONDITIONAL rule_type criteria (companies < 3 years old get
    # a different threshold calculation in the rules engine).
    company_age_years: Mapped[float | None] = mapped_column(Float, nullable=True)

    overall_verdict: Mapped[OverallVerdict] = mapped_column(
        Enum(OverallVerdict), default=OverallVerdict.PENDING, nullable=False
    )

    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )