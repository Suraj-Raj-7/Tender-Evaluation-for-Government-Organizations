"""
backend/app/schemas/bidder.py
--------------------------------
Purpose: Defines the JSON shapes for registering a bidder against a
tender, viewing bidder data, and a bidder's self-registration form.

NOTE: BidderRegister below includes 'phone', which currently has no
matching column in the Bidder or User model. Flagged for a decision
before the registration router is built.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.bidder import BidderCategory, OverallVerdict


class BidderCreate(BaseModel):
    """
    Purpose: Shape of data for registering a company against one tender.
    Where it's used: POST /tenders/{id}/bidders request body.
    """
    company_name: str
    gstin: str | None = None
    cin: str | None = None
    category: BidderCategory = BidderCategory.GENERAL


class BidderResponse(BaseModel):
    """
    Purpose: Shape of bidder data returned to the frontend.
    Where it's used: Returned by GET /tenders/{id}/bidders.
    """
    id: int
    company_name: str
    category: BidderCategory
    overall_verdict: OverallVerdict
    applied_at: datetime

    model_config = {"from_attributes": True}


class BidderRegister(BaseModel):
    """
    Purpose: Shape of the self-registration form a new bidder company
    fills out (creates both a User login and, later, Bidder rows per
    tender they apply to).
    Where it's used: POST /auth/register-bidder request body.
    """
    company_name: str
    gstin: str
    email: EmailStr
    phone: str
    password: str