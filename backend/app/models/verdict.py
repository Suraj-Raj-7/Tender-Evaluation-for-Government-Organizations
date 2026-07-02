"""
backend/app/models/verdict.py
--------------------------------
Purpose: Defines the Verdict table (the decision for one Evidence row --
PASS/FAIL/REVIEW) and the Override table (a permanent log entry every
time an officer changes a verdict).

Why this file exists: Splitting "decision" (Verdict) from "evidence"
(previous file) and further splitting "current decision" (Verdict) from
"change history" (Override) gives a complete, tamper-evident trail: what
the AI found, what it initially decided, and every human change since.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class VerdictEnum(str, enum.Enum):
    """
    Purpose: The three possible outcomes for one criterion.
    Where it's used: Verdict.ai_verdict, Verdict.final_verdict, and
    Override.from_verdict/to_verdict columns below. Produced by the
    rules engine in Phase 4 (never guessed, always deterministic).
    """
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class Verdict(Base):
    """
    Purpose: One row per Evidence row, holding the decision. ai_verdict
    is set once and never changed. final_verdict starts equal to
    ai_verdict, and is the only field an override updates.

    Where it's used: Created once by the rules engine in Phase 4, right
    after each Evidence row. routers/evaluation.py's override endpoint
    updates final_verdict and is_overridden here (but never ai_verdict).
    """
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # One-to-one with Evidence -- unique means each Evidence row gets
    # exactly one Verdict row.
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), unique=True, nullable=False)

    # What the rules engine originally decided. Never changes after creation.
    ai_verdict: Mapped[VerdictEnum] = mapped_column(Enum(VerdictEnum), nullable=False)

    # The current, active decision. Equals ai_verdict unless overridden.
    final_verdict: Mapped[VerdictEnum] = mapped_column(Enum(VerdictEnum), nullable=False)

    is_overridden: Mapped[bool] = mapped_column(default=False, nullable=False)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Override(Base):
    """
    Purpose: One row per override action. Append-only -- if an officer
    overrides the same verdict twice, that creates two Override rows,
    not one edited row.

    Where it's used: Created by routers/evaluation.py's
    POST /verdicts/{id}/override endpoint (built in Phase 4). Displayed
    in the Evidence Panel's override history (Phase 5) and in audit
    reports (Phase 6).
    """
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    verdict_id: Mapped[int] = mapped_column(ForeignKey("verdicts.id"), nullable=False)

    # Which Evaluator performed this override.
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    from_verdict: Mapped[VerdictEnum] = mapped_column(Enum(VerdictEnum), nullable=False)

    to_verdict: Mapped[VerdictEnum] = mapped_column(Enum(VerdictEnum), nullable=False)

    # Mandatory (min 10 chars, enforced in the schema layer) -- this is
    # what makes an override legally defensible, not just a silent change.
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    overridden_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )