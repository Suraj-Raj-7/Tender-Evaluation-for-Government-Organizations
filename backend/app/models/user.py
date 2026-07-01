"""
backend/app/models/user.py
----------------------------
Purpose: Defines the User table -- every person who can log in to TenderIQ
(System Admin, Publisher, Bidder, Evaluator, Auditor all share this one
table, distinguished by their 'role' column). Also defines
PasswordResetToken, used when a password is reset.

Why this file exists: Every login, permission check, and account action
in the whole platform starts from this table. It is the foundation every
other model (Tender, Bidder, Evidence, etc.) will reference.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RoleEnum(str, enum.Enum):
    """
    Purpose: The five fixed roles in the system. Stored as text in the
    database (e.g. 'EVALUATOR'), but restricted to only these five values.

    Where it's used: User.role column below, and in require_role() calls
    throughout the routers we build later.
    """
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    PUBLISHER = "PUBLISHER"
    BIDDER = "BIDDER"
    EVALUATOR = "EVALUATOR"
    AUDITOR = "AUDITOR"


class User(Base):
    """
    Purpose: One row per person who can log in. Login, JWT tokens, and
    role-based permission checks all read from this table.

    Where it's used: dependencies.py's get_current_user() loads a User
    row on every protected request. routers/auth.py and routers/admin.py
    create new User rows.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Login name, must be unique across the whole platform.
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Used for sending credentials/notifications (e.g. temp password emails).
    email: Mapped[str] = mapped_column(String(200), nullable=False)

    # Which department this officer belongs to (Publisher/Evaluator/Auditor only).
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Never store real passwords -- only the Argon2 hash from security.py.
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)

    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)

    # Deactivated accounts are hidden from login but never deleted (audit trail).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Counts consecutive failed logins. Account locks after 5 (per spec).
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Set when an account gets locked after too many failed attempts.
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PasswordResetToken(Base):
    """
    Purpose: A one-time-use token issued when a user's password needs to
    be reset (e.g. bidder email verification link, admin-triggered reset).

    Where it's used: routers/auth.py (bidder email verification) and
    routers/admin.py (admin password reset flow) will create and check
    rows in this table.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # The random token string sent in an email link.
    token: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # True once the token has been used, so it can't be reused.
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)