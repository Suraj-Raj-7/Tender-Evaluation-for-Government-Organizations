# Audit Bundle exports
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.models import AuditLog, Tender
from app.deps import require_user

router = APIRouter(prefix="/reports", tags=["Audit"])

@router.get("/{tender_id}/audit-log")
def get_system_logs(tender_id: int, db: SASession = Depends(get_db), user = Depends(require_user)):
    """Returns logs for the Auditor view."""
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()

@router.get("/{tender_id}/export")
def export_bundle(tender_id: int, db: SASession = Depends(get_db), user = Depends(require_user)):
    """Placeholder for PDF/Evidence bundle generation[cite: 1, 2]."""
    return {"msg": "Audit bundle generation started. Link will be sent to email."}