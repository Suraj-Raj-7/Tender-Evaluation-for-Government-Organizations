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
from app.models.verdict import Override
from app.models.verdict import Verdict
from app.models.evidence import Evidence
from app.models.bidder import Bidder
from app.models.tender import Tender
from app.models.criterion import Criterion
from app.models.job import Job, JobStatus
from app.schemas.audit import AuditLogResponse, OverrideDetailResponse, AuditStatsResponse

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


@router.get("/overrides", response_model=list[OverrideDetailResponse])
def list_all_overrides(
    current_user: User = Depends(require_role(RoleEnum.AUDITOR.value, RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Lists every override ever made, platform-wide, with the
    officer's real name and enough tender/bidder/criterion context to
    read on its own -- including the override's reason, which a plain
    AuditLog row never contains.

    Where it gets its data: joins Override -> Verdict -> Evidence ->
    Bidder -> Tender, and Override -> User (for the officer's name).

    Where it's used: called by the frontend's AuditLog.jsx Overrides
    tab.
    """
    rows = (
        db.query(Override, User, Tender, Bidder, Criterion)
        .join(User, User.id == Override.officer_id)
        .join(Verdict, Verdict.id == Override.verdict_id)
        .join(Evidence, Evidence.id == Verdict.evidence_id)
        .join(Bidder, Bidder.id == Evidence.bidder_id)
        .join(Tender, Tender.id == Bidder.tender_id)
        .join(Criterion, Criterion.id == Evidence.criterion_id)
        .order_by(Override.overridden_at.desc())
        .all()
    )

    return [
        OverrideDetailResponse(
            id=override.id,
            officer_name=user.full_name,
            tender_id=tender.id,
            tender_name=tender.name,
            bidder_company_name=bidder.company_name,
            criterion_code=criterion.code,
            from_verdict=override.from_verdict.value,
            to_verdict=override.to_verdict.value,
            reason=override.reason,
            overridden_at=override.overridden_at,
        )
        for override, user, tender, bidder, criterion in rows
    ]


@router.get("/stats", response_model=AuditStatsResponse)
def get_audit_stats(
    current_user: User = Depends(require_role(RoleEnum.AUDITOR.value, RoleEnum.SYSTEM_ADMIN.value)),
    db: Session = Depends(get_db),
):
    """
    Purpose: Platform-wide counters for the Audit Log page's summary
    cards -- currently just the count of failed background jobs
    (documents that failed OCR or AI extraction), which isn't visible
    from anywhere else in the Auditor's view.

    Where it's used: called by the frontend's AuditLog.jsx to power
    the "Extraction Errors" stat card.
    """
    extraction_error_count = db.query(Job).filter(Job.status == JobStatus.FAILED).count()
    return AuditStatsResponse(extraction_error_count=extraction_error_count)