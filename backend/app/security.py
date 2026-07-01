"""
backend/app/security.py
------------------------
Purpose: Handles two things -- (1) turning plain passwords into unreadable
hashes and checking them back, and (2) creating and verifying JWT login
tokens.

Why this file exists: No other file should touch raw passwords or write
JWT logic directly. Centralizing it here means there is exactly one place
that knows how hashing and tokens work, which is safer and easier to audit.
"""

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, status
from app.config import settings


# Argon2 is the current recommended password hashing algorithm --
# resistant to GPU cracking attempts. One shared instance is reused
# everywhere in this file.
ph = PasswordHasher()

# Tokens expire after 8 hours (per the project spec) -- user must re-login after that.
ACCESS_TOKEN_EXPIRE_HOURS = 8

# The algorithm used to sign JWT tokens.
ALGORITHM = "HS256"


def hash_password(plain_password: str) -> str:
    """
    Purpose: Converts a plain text password into an unreadable hash before
    it is ever stored in the database.

    Where it's used: In routers/auth.py during registration, and in
    routers/admin.py when creating officer accounts.

    Where it gets its data: Called with whatever raw password string the
    user typed into a registration/creation form.
    """
    return ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Purpose: Checks if a plain password typed at login matches the stored
    hash, without ever un-scrambling the hash.

    Where it's used: In routers/auth.py's login endpoint.

    Where it gets its data: plain_password comes from the login form.
    hashed_password comes from the matching User row's password_hash
    column, fetched from the database.
    """
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: int, role: str) -> str:
    """
    Purpose: Creates a signed JWT token proving who the user is and what
    role they have, valid for 8 hours.

    Where it's used: In routers/auth.py, right after a successful login,
    to generate the token sent back to the frontend.

    Where it gets its data: user_id and role come from the User row that
    was just successfully authenticated.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """
    Purpose: Checks that a JWT token is validly signed and not expired,
    and returns its contents (user_id, role) if so.

    Where it's used: In dependencies.py's get_current_user(), which runs
    on every protected API request to identify who is calling it.

    Where it gets its data: The raw token string, extracted from the
    'Authorization: Bearer <token>' header of an incoming request.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )