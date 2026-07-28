"""
backend/app/schemas/audit.py
--------------------------------
Purpose: JSON shape for one audit log entry, returned to the Auditor's log viewer.
"""

from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """One audit log row. Used by: GET /audit."""
    id: int
    user_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    old_value: dict | None
    new_value: dict | None
    ip_address: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


class OverrideDetailResponse(BaseModel):
    """
    Purpose: One override, enriched with the real officer name and
    enough tender/bidder/criterion context to be meaningful on its
    own -- unlike a raw AuditLog row, this includes the override's
    reason text, which only ever lives on the Override table itself.

    Where it's used: Returned by GET /audit/overrides, for the
    Auditor's dedicated Overrides tab.
    """
    id: int
    officer_name: str
    tender_id: int
    tender_name: str
    bidder_company_name: str
    criterion_code: str
    from_verdict: str
    to_verdict: str
    reason: str
    overridden_at: datetime

    model_config = {"from_attributes": True}


class AuditStatsResponse(BaseModel):
    """
    Purpose: Small set of platform-wide counters for the Audit Log
    page's summary cards -- specifically the count of failed
    background extraction jobs (OCR/AI failures), which isn't
    otherwise visible anywhere in the Auditor's view.

    Where it's used: Returned by GET /audit/stats.
    """
    extraction_error_count: int