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