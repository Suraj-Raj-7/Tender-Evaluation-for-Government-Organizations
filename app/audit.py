# app/audit.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import AuditLog

def log(db: Session, username: str, action: str, details: dict):
    """
    Records an immutable audit entry.
    Useful for tracking AI extractions and manual overrides.
    """
    entry = AuditLog(
        username=username,
        action=action,
        timestamp=datetime.utcnow(),
        details=str(details) # Stores tender/bidder IDs for tracking
    )
    db.add(entry)
    db.commit()
    print(f"[AUDIT] {username} performed {action} - {details}")