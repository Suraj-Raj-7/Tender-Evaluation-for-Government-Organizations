# Login/Logout/Role switching
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as SASession
from app.db import get_db
from app.security import authenticate, create_session, destroy_session
from app.deps import SESSION_COOKIE, current_user
from app.audit import log

router = APIRouter()

@router.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: SASession = Depends(get_db)):
    user, err = authenticate(db, username, password)
    if not user:
        return RedirectResponse("/login?error=" + err, status_code=303)
    
    sess = create_session(db, user, request.client.host if request.client else "")
    log(db, user.username, "LOGIN_SUCCESS")
    
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE, sess.id,
        httponly=True, samesite="lax", secure=False, path="/"
    )
    return resp

@router.post("/logout")
def logout(request: Request, db: SASession = Depends(get_db)):
    sid = request.cookies.get(SESSION_COOKIE) or ""
    destroy_session(db, sid)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp