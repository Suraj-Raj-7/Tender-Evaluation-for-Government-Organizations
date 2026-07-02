"""
backend/app/models/audit.py
------------------------------
Purpose: Defines the AuditLog table -- one row per significant action
taken anywhere in the system (login, override, document view, etc.).
Append-only: no code should ever UPDATE or DELETE a row here.

Why this file exists: This table is what makes TenderIQ usable for CAG
audits and RTI Act 2005 requests. A complete, tamper-evident timeline
of every action, who did it, and when.
"""

from datetime import datetime, timezone
from sqlalchemy import Integer, String, JSON, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AuditLog(Base):
    """
    Purpose: One row per logged action across the whole platform.

    Where it's used: Written by services/audit_logger.py's log_action()
    function (built in Phase 6, but called from routers throughout every
    phase). Read by routers/audit.py for the Auditor's audit log viewer.

    IMPORTANT: Never call db.query(AuditLog)...update() or .delete()
    anywhere in this codebase. Every action is a brand new row.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Nullable in case an action happens without a logged-in user (rare, e.g. system events).
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # e.g. "LOGIN", "VERDICT_OVERRIDE", "DOCUMENT_VIEWED", "EVALUATION_COMPLETE".
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Which type of record this action relates to, e.g. "tender", "verdict".
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Snapshot of the record's state before/after the action, for changes
    # like overrides (e.g. old_value={"verdict": "FAIL"}, new_value={"verdict": "PASS"}).
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )