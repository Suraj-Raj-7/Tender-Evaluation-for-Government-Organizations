# Argon2 hashing & Session management
import secrets
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session as SASession
from app.models import User, Session as DbSession

_ph = PasswordHasher()
SESSION_TTL_HOURS = 8

def hash_password(pw: str) -> str:
    return _ph.hash(pw)

def verify_password(hash_: str, pw: str) -> bool:
    try:
        return _ph.verify(hash_, pw)
    except VerifyMismatchError:
        return False

def authenticate(db: SASession, username: str, password: str) -> tuple[User | None, str]:
    user = db.query(User).filter_by(username=username).first()
    if not user or not user.is_active:
        return None, "Invalid credentials"
    if not verify_password(user.password_hash, password):
        return None, "Invalid credentials"
    return user, ""

def create_session(db: SASession, user: User, ip: str = "") -> DbSession:
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    s = DbSession(
        id=sid, user_id=user.id, csrf_token=csrf,
        expires_at=datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS),
        ip_address=ip,
    )
    db.add(s)
    db.commit()
    return s

def get_session(db: SASession, sid: str) -> DbSession | None:
    if not sid:
        return None
    s = db.get(DbSession, sid)
    if not s or s.expires_at < datetime.utcnow():
        return None
    return s

def destroy_session(db: SASession, sid: str):
    s = db.get(DbSession, sid)
    if s:
        db.delete(s)
        db.commit()