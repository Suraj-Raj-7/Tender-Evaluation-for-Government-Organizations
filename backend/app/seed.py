"""
backend/app/seed.py
----------------------
Purpose: Creates the very first System Administrator account when
TenderIQ is deployed on a completely empty database. Without this,
there would be no way to log in at all, since only an admin can
create other accounts (Publisher/Evaluator/Auditor), and bidders
self-register but can't do anything until tenders exist.

Why this file exists: Called once from main.py's startup event. Safe
to call on every server restart -- it checks first, so it never
creates a duplicate admin account.
"""

from sqlalchemy.orm import Session
from app.models.user import User, RoleEnum
from app.security import hash_password
from app.config import settings


def run_seed(db: Session):
    """
    Purpose: Creates the first admin account if (and only if) no users
    exist yet in the database.

    Where it's used: Called once from main.py, right after init_db()
    runs at server startup.

    Where it gets its data: The admin's password comes from
    settings.FIRST_ADMIN_PASSWORD (from .env) -- never hardcoded here.
    """
    existing_user_count = db.query(User).count()

    if existing_user_count > 0:
        # Not the first run -- an admin (or other users) already exist.
        return

    admin = User(
        username="admin",
        full_name="System Administrator",
        email="admin@tenderiq.local",
        password_hash=hash_password(settings.FIRST_ADMIN_PASSWORD),
        role=RoleEnum.SYSTEM_ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()

    # Printed to the terminal so you can see it once, the first time you
    # ever start the server. This is not a security risk since it's your
    # own local terminal, not exposed anywhere.
    print("=" * 60)
    print("FIRST-TIME SETUP: Admin account created")
    print(f"  Username: admin")
    print(f"  Password: {settings.FIRST_ADMIN_PASSWORD}")
    print("  Change this password immediately after first login.")
    print("=" * 60)