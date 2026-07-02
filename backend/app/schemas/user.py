"""
backend/app/schemas/user.py
------------------------------
Purpose: Defines the JSON shapes for user-related API requests and
responses -- registration, login, account info, and admin-driven
account creation.

Why this file exists: These are NOT database models. UserResponse
deliberately excludes password_hash so it can never accidentally leak
in an API response, even if a developer forgets to filter it manually.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.user import RoleEnum


class UserCreate(BaseModel):
    """
    Purpose: Generic shape for creating a user with a caller-supplied
    password. Currently unused by the admin creation flow (which
    generates its own password) -- kept for any future flow that needs it.
    """
    username: str
    full_name: str
    password: str
    role: RoleEnum
    email: EmailStr


class AdminUserCreate(BaseModel):
    """
    Purpose: Shape of data an admin submits to create a new officer
    account. Deliberately has NO password field -- the system generates
    a temporary password itself (see security.py's generate_temp_password).
    Where it's used: POST /admin/users request body (Admin only).
    """
    username: str
    full_name: str
    role: RoleEnum
    email: EmailStr
    department: str | None = None


class AdminUserStatusUpdate(BaseModel):
    """
    Purpose: Shape of a request to deactivate or reactivate a user account.
    Where it's used: PATCH /admin/users/{id} request body (Admin only).
    """
    is_active: bool


class UserResponse(BaseModel):
    """
    Purpose: Safe shape of user data to send back to the client.
    Deliberately excludes password_hash.
    Where it's used: Returned by GET /auth/me, GET /admin/users, etc.
    """
    id: int
    username: str
    full_name: str
    role: RoleEnum
    is_active: bool
    created_at: datetime

    # Allows creating this schema directly from a SQLAlchemy User object,
    # not just a plain dict.
    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    """
    Purpose: Shape of the login form submission.
    Where it's used: POST /auth/login request body.
    """
    username: str
    password: str


class TokenResponse(BaseModel):
    """
    Purpose: Shape of a successful login response -- the JWT and basic
    identity info the frontend needs immediately (e.g. to route by role).
    Where it's used: Returned by POST /auth/login.
    """
    access_token: str
    token_type: str = "bearer"
    role: RoleEnum
    user_id: int


class PasswordChangeRequest(BaseModel):
    """
    Purpose: Shape of a password change request -- requires the current
    password as proof, even though the user is already logged in.
    Where it's used: POST /auth/change-password request body.
    """
    current_password: str
    new_password: str = Field(min_length=8)