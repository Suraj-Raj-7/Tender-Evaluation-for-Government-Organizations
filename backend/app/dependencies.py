"""
backend/app/dependencies.py
----------------------------
Purpose: Provides reusable "gatekeeper" functions that protected routes
plug in to check who is calling them and whether they're allowed to.

Why this file exists: Without this, every single route would need to
manually decode the token, look up the user, and check their role --
repeated dozens of times. FastAPI's Depends() system lets routes just
declare "I need a valid, authorized user" and this file supplies it.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import verify_token
from app.models.user import User


# auto_error=False so we can raise our own 401 (not FastAPI's default 403)
# when no token is provided at all -- 401 means "not identified", 403
# means "identified but not allowed", and the spec requires 401 here.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Purpose: Identifies which user is making the current request.

    Where it's used: As a dependency in almost every protected route
    (e.g. "GET /auth/me", "POST /tenders"). Routes declare:
    current_user: User = Depends(get_current_user)

    Where it gets its data: 'credentials' is auto-extracted by FastAPI
    from the Authorization header of the incoming request (None if the
    header is missing entirely). 'db' is a database session from
    database.py's get_db().

    What it does: If no token was provided, raises 401 immediately.
    Otherwise verifies the token's signature and expiry (via
    security.py's verify_token), then loads the matching User row from
    the database. Raises 401 for any identity failure -- 403 is reserved
    for "you are known, but not permitted" (see require_role below).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )
    return user


def require_role(*allowed_roles: str):
    """
    Purpose: Builds a dependency that only lets a request through if the
    current user's role is one of the allowed roles for that route.

    Where it's used: In routers, e.g.:
    current_user: User = Depends(require_role("PUBLISHER"))
    This runs get_current_user() first (to know who they are), then
    checks their role.

    Where it gets its data: allowed_roles are hardcoded per-route by
    whoever writes that route (e.g. only "EVALUATOR" can override a verdict).

    Why it's a function that returns a function: FastAPI's Depends()
    needs a callable with no extra arguments at call time, but we need
    to customize *which* roles are allowed per route. This pattern lets
    us write require_role("PUBLISHER") and get a ready-to-use dependency.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_checker