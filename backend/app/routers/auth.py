"""
backend/app/routers/auth.py
------------------------------
Purpose: Handles login, checking who you are, changing your password,
and bidder self-registration.

Why this file exists: This is the entry point for every user into the
platform -- the very first request anyone makes (except a bidder
registering) is a login here.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, RoleEnum
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    PasswordChangeRequest,
)
from app.schemas.bidder import BidderRegister
from app.security import hash_password, verify_password, create_access_token
from app.services.audit_logger import log_action

router = APIRouter(prefix="/auth", tags=["auth"])

# After this many consecutive failed logins, an account locks and only
# an admin can unlock it (per project spec 3.4).
MAX_FAILED_ATTEMPTS = 5


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Purpose: Authenticates a user and issues a JWT token valid for 8 hours.

    Where it gets its data: request.username/password come from the
    login form on the frontend. Matching User row is looked up in the
    database via db.

    Where it's used: Called by the frontend's Login page on form submit.
    """
    user = db.query(User).filter(User.username == request.username).first()

    # Deliberately vague error message (don't reveal whether the
    # username or password was wrong -- prevents username enumeration).
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
    )

    if user is None:
        raise invalid_credentials_error

    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account locked due to too many failed attempts. Contact your administrator.",
        )

    if not verify_password(request.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc)
        db.commit()
        raise invalid_credentials_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    # Successful login -- reset the failed attempt counter.
    user.failed_attempts = 0
    log_action(
        db,
        user_id=user.id,
        action="LOGIN",
        entity_type="user",
        entity_id=user.id,
        ip_address=http_request.client.host if http_request.client else None,
    )
    db.commit()

    token = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Purpose: Returns the currently logged-in user's own info -- used by
    the frontend right after login to know who they are and route them
    to the correct dashboard by role.

    Where it gets its data: current_user comes from get_current_user(),
    which already decoded and verified the JWT token in the request header.
    """
    return current_user


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Purpose: Confirms a logout request. Note: JWT tokens are stateless
    (see security.py) -- the server can't forcibly invalidate a token
    early. Real "logout" happens on the frontend by deleting the token
    from sessionStorage. This endpoint exists mainly so a logout action
    is confirmed and traceable.

    Where it's used: Called by the frontend when the user clicks Logout.
    """
    return {"message": "Logged out successfully"}


@router.post("/change-password")
def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Purpose: Lets a logged-in user change their own password, proving
    they know the current one first.

    Where it gets its data: request.current_password/new_password come
    from the Settings page form. current_user identifies whose password
    to change.
    """
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/register-bidder", response_model=UserResponse)
def register_bidder(request: BidderRegister, db: Session = Depends(get_db)):
    """
    Purpose: Self-registration for bidder companies -- the only role
    that doesn't need an admin to create their account.

    Where it gets its data: request fields come from the "Register as
    Bidder" form on the frontend's login page.

    Note: Real email sending (verification links) is built in Phase 6's
    notification service. For now, the account is created active
    immediately so registration is usable end-to-end while that service
    doesn't exist yet.
    """
    existing = db.query(User).filter(User.username == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    new_bidder = User(
        username=request.email,
        full_name=request.company_name,
        email=request.email,
        company_name=request.company_name,
        gstin=request.gstin,
        phone=request.phone,
        password_hash=hash_password(request.password),
        role=RoleEnum.BIDDER,
        is_active=True,
    )
    db.add(new_bidder)
    db.commit()
    db.refresh(new_bidder)
    return new_bidder