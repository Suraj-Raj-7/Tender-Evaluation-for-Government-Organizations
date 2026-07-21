"""
backend/app/schemas/bidder.py
--------------------------------
Purpose: Defines the JSON shapes for registering a bidder against a
tender, viewing bidder data, a bidder's self-registration form, and
(new in Phase 5) a bidder's own view of all their applications.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.bidder import BidderCategory, OverallVerdict
from app.models.tender import TenderStatus


class BidderCreate(BaseModel):
    """Shape of data for registering a company against one tender.
    Where it's used: POST /tenders/{id}/bidders request body."""
    company_name: str
    gstin: str | None = None
    cin: str | None = None
    category: BidderCategory = BidderCategory.GENERAL


class BidderResponse(BaseModel):
    """Shape of bidder data returned to the frontend.
    Where it's used: Returned by GET /tenders/{id}/bidders."""
    id: int
    company_name: str
    category: BidderCategory
    overall_verdict: OverallVerdict
    applied_at: datetime

    model_config = {"from_attributes": True}


class BidderRegister(BaseModel):
    """Shape of the self-registration form a new bidder company fills out.
    Where it's used: POST /auth/register-bidder request body."""
    company_name: str
    gstin: str
    email: EmailStr
    phone: str
    password: str


class MyApplicationResponse(BaseModel):
    """
    Purpose: One row in a bidder's own \"My Applications\" list --
    combines their Bidder row with the parent Tender's name/status/
    deadline, so BidderPortal.jsx can render everything from one API
    call instead of fetching each tender separately.

    Where it's used: Returned by GET /bidders/me (new in Phase 5,
    added because no endpoint previously let a bidder see their own
    applications across tenders -- routers/bidders.py only had
    apply-to-tender and the Evaluator/Auditor-only list-bidders route).
    """
    id: int
    tender_id: int
    tender_name: str
    tender_status: TenderStatus
    tender_deadline: datetime
    company_name: str
    category: BidderCategory
    overall_verdict: OverallVerdict
    applied_at: datetime

    model_config = {"from_attributes": True}