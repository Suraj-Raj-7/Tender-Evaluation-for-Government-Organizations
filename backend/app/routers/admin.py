"""
backend/app/routers/admin.py
-------------------------------
Purpose: Endpoints only the System Administrator can use -- creating
officer accounts, listing all users, deactivating/reactivating accounts,
and resetting passwords.

Why this file exists: Per the project's access model, only one role
manages accounts platform-wide. Every endpoint here is locked to
SYSTEM_ADMIN via require_role.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User, RoleEnum
from app.schemas.user import AdminUserCreate, AdminUserStatusUpdate, UserResponse
from app.security import hash_password, generate_temp_password

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserResponse)
def create_officer_account(
    request: AdminUserCreate,
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Creates a PUBLISHER, EVALUATOR, or AUDITOR account (never
    used for BIDDER -- those self-register via auth.py).

    Where it gets its data: request fields come from the Admin Panel's
    "Create New User" form. current_user is checked to be a SYSTEM_ADMIN
    before this function even runs (via require_role).

    Note: A random temp password is generated here, hashed before
    storing, and printed to the console. Real email delivery will
    replace the console print once Phase 6's notification service exists.
    """
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists",
        )

    temp_password = generate_temp_password()

    new_user = User(
        username=request.username,
        full_name=request.full_name,
        email=request.email,
        department=request.department,
        password_hash=hash_password(temp_password),
        role=request.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    print("=" * 60)
    print(f"New {request.role.value} account created")
    print(f"  Username: {request.username}")
    print(f"  Temporary password: {temp_password}")
    print("  User must change this on first login.")
    print("=" * 60)

    return new_user


@router.get("/users", response_model=list[UserResponse])
def list_all_users(
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Returns every user account on the platform, for the Admin
    Panel's user management table.

    Where it gets its data: Queries every row in the users table.
    """
    return db.query(User).all()


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user_status(
    user_id: int,
    request: AdminUserStatusUpdate,
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Deactivates or reactivates a user account. Accounts are
    never deleted, per spec 2.1 -- this preserves the audit trail.

    Where it gets its data: user_id comes from the URL path.
    request.is_active comes from the Admin Panel's toggle action.

    Note: Reactivating an account also clears failed_attempts and
    locked_until -- this is how an admin "unlocks" an account that got
    locked after 5 failed login attempts (per spec 3.4).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = request.is_active
    if request.is_active:
        user.failed_attempts = 0
        user.locked_until = None

    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Generates a brand new temporary password for a user who
    forgot theirs, and unlocks the account if it was locked.

    Where it gets its data: user_id comes from the URL path (which
    account to reset).

    Note: Same as account creation -- prints to console for now, until
    Phase 6's email service exists.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    temp_password = generate_temp_password()
    user.password_hash = hash_password(temp_password)
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    print("=" * 60)
    print(f"Password reset for user: {user.username}")
    print(f"  New temporary password: {temp_password}")
    print("=" * 60)

    return {"message": "Password reset successfully. New credentials printed to server console."}