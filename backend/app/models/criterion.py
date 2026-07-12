"""
backend/app/models/criterion.py
---------------------------------
Purpose: Defines the Criterion table -- one row per eligibility rule
extracted from a tender's NIT document (e.g. "Turnover >= 128L",
"GST registration required"). Criteria are never hardcoded; they are
always extracted fresh per tender and stored as rows here.

Why this file exists: The rules engine (built in Phase 4) reads these
rows to know what to check for each bidder. threshold_json holds
whatever data shape a specific rule_type needs, since no two tenders
have identical criteria.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, Boolean, Enum, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CriterionCategory(str, enum.Enum):
    """
    Purpose: Groups a criterion by what kind of requirement it is.
    Where it's used: Criterion.category column below.
    """
    FINANCIAL = "FINANCIAL"
    TECHNICAL = "TECHNICAL"
    COMPLIANCE = "COMPLIANCE"
    LEGAL = "LEGAL"
    DECLARATION = "DECLARATION"


class RuleType(str, enum.Enum):
    """
    Purpose: Tells the rules engine (Phase 4) which of the 8 evaluation
    functions to run for this criterion.
    Where it's used: Criterion.rule_type column below.
    """
    NUMERIC_THRESHOLD = "NUMERIC_THRESHOLD"
    CONDITIONAL = "CONDITIONAL"
    NO_LOSS = "NO_LOSS"
    QUANTITY_PCT = "QUANTITY_PCT"
    BOOLEAN = "BOOLEAN"
    DOC_PRESENCE = "DOC_PRESENCE"
    CLASSIFICATION = "CLASSIFICATION"
    COMPOSITE = "COMPOSITE"


class Criterion(Base):
    """
    Purpose: One row per eligibility rule for one specific tender.
    A tender with 18 criteria has 18 rows here, all sharing the same
    tender_id.

    Where it's used: Created by the AI extraction pipeline in Phase 3
    (tender_parser.py), editable by the Publisher via routers/criteria.py,
    and read by the rules engine in Phase 4 to evaluate each bidder.
    """
    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), nullable=False)

    # Short identifier shown in the UI matrix column header, e.g. "C1", "C2".
    code: Mapped[str] = mapped_column(String(10), nullable=False)

    category: Mapped[CriterionCategory] = mapped_column(Enum(CriterionCategory), nullable=False)

    # The full legal text of the requirement, shown on column-header hover.
    description: Mapped[str] = mapped_column(Text, nullable=False)

    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType), nullable=False)

    # Comparison operator this rule uses, e.g. ">=", "<=", "==", "NOT_IN".
    operator: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Flexible JSON data shape -- content depends on rule_type.
    # e.g. {"value": 128, "unit": "Lakhs", "years": 3} for NUMERIC_THRESHOLD.
    threshold_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    # If True, failing this criterion makes the whole bidder NOT_ELIGIBLE.
    # If False, a failure is only noted, not disqualifying.
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional hint for the AI on where to look for evidence (e.g. "CA certificate").
    evidence_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    # True if MSME/Startup bidders are exempt from this specific criterion.
    msme_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)