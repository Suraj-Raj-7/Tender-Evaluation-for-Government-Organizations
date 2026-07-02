"""
backend/app/routers/audit.py
-------------------------------
Purpose: Lets Auditors (and Admins) view the platform's immutable audit
log, with optional filters. Real log entries only start appearing once
routers call the audit logging service (built in Phase 6) -- this
endpoint just reads whatever rows already exist.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User, RoleEnum
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_log(
    tender_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_role(RoleEnum.AUDITOR.value, RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Returns filtered, paginated audit log entries. All filter params are
    optional query params, e.g. GET /audit?action=LOGIN&page=2.
    """
    query = db.query(AuditLog)

    if tender_id is not None:
        query = query.filter(AuditLog.entity_id == tender_id, AuditLog.entity_type == "tender")
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if date_from is not None:
        query = query.filter(AuditLog.timestamp >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.timestamp <= date_to)

    offset = (page - 1) * per_page
    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(per_page).all()