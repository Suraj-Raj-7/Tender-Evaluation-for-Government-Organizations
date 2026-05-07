# RBAC Dependencies (current_user, require_roles)
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.models import User, Role, Session as DbSession
from app.security import get_session

SESSION_COOKIE = "crpf_sid"

def current_session(request: Request, db: SASession = Depends(get_db)):
    sid = request.cookies.get(SESSION_COOKIE)
    return get_session(db, sid or "")

def current_user(request: Request, db: SASession = Depends(get_db)) -> User | None:
    s = current_session(request, db)
    if not s:
        return None
    return db.get(User, s.user_id)

def require_user(user: User | None = Depends(current_user)) -> User:
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

def require_roles(*roles: Role):
    def _dep(user: User = Depends(require_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden for your role")
        return user
    return _dep