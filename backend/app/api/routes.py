from datetime import timedelta
import hmac
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.database.store import now
from app.models.entities import Admin, User, Session, SecurityEvent
from app.security.credentials import digest, verify_password, hash_password

router = APIRouter(prefix="/api")
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def database(request: Request):
    with request.app.state.session_factory() as db:
        # Serialize SQLite write transactions, including risk/session updates.
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except HTTPException:
            db.commit()  # Preserve security evidence for denied requests.
            raise
        except Exception:
            db.rollback()
            raise


def record(db, request, kind, user_id=None, session=None, outcome="success"):
    db.add(SecurityEvent(user_id=user_id, session_id=session.id if session else None,
        ip=request.client.host if request.client else "unknown", event_type=kind,
        endpoint=request.url.path, outcome=outcome,
        state_before=session.state if session else "LOGGED_OUT",
        state_after=session.state if session else "LOGGED_OUT"))
    db.flush()


def identity(request: Request, db=Depends(database), admin=False):
    cookie = "pg_admin" if admin else "pg_bank"
    raw = request.cookies.get(cookie, "")
    session = db.get(Session, digest(raw)) if raw else None
    if not session or session.revoked or session.expires_at <= now():
        record(db, request, "UNAUTHORIZED_REQUEST", outcome="denied")
        raise HTTPException(401, "Authentication required")
    person = db.get(Admin if admin else User, session.admin_id if admin else session.user_id) if (session.admin_id if admin else session.user_id) else None
    if not person:
        raise HTTPException(403, "Role not permitted")
    if not admin and person.blocked:
        record(db, request, "ACCESS_BLOCKED", person.id, session, "denied")
        raise HTTPException(403, "Account access restricted")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(digest(csrf), session.csrf_hash):
            raise HTTPException(403, "Invalid CSRF token")
    return person, session


def bank_identity(request: Request, db=Depends(database)):
    return identity(request, db, False)


def admin_identity(request: Request, db=Depends(database)):
    return identity(request, db, True)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def login(data, request, response, db, admin):
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.cors_origins.split(","):
        raise HTTPException(403, "Origin not permitted")
    ip = request.client.host if request.client else "unknown"
    recent = db.scalar(select(func.count()).select_from(SecurityEvent).where(
        SecurityEvent.ip == ip, SecurityEvent.event_type == "LOGIN_ATTEMPT",
        SecurityEvent.created_at > now() - timedelta(minutes=1)))
    if recent >= 20:
        record(db, request, "RATE_LIMIT_TRIGGERED", outcome="denied")
        raise HTTPException(429, "Too many login attempts. Try again later.")
    table = Admin if admin else User
    person = db.scalar(select(table).where(table.username == data.username))
    uid = person.id if person and not admin else None
    record(db, request, "LOGIN_ATTEMPT", uid)
    if not verify_password(data.password, person.password_hash if person else DUMMY_HASH):
        record(db, request, "LOGIN_FAILED", uid, outcome="denied")
        raise HTTPException(401, "Invalid username or password")
    if not admin and person.blocked:
        record(db, request, "ACCESS_BLOCKED", uid, outcome="denied")
        raise HTTPException(403, "Account access restricted")
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session = Session(id=digest(token), csrf_hash=digest(csrf), user_id=None if admin else person.id,
        admin_id=person.id if admin else None, expires_at=now()+timedelta(hours=2))
    db.add(session)
    db.flush()
    record(db, request, "LOGIN_SUCCESS", uid, session)
    response.set_cookie("pg_admin" if admin else "pg_bank", token, httponly=True,
        secure=request.app.state.settings.protocolguard_env != "development", samesite="strict", max_age=7200)
    return {"username": person.username, "csrf_token": csrf, "role": "admin" if admin else "user"}


@router.post("/auth/login")
def bank_login(data: Login, request: Request, response: Response, db=Depends(database)):
    return login(data, request, response, db, False)


@router.post("/admin/auth/login")
def admin_login(data: Login, request: Request, response: Response, db=Depends(database)):
    return login(data, request, response, db, True)


@router.get("/auth/me")
def me(auth=Depends(bank_identity)):
    return {"username": auth[0].username, "role": "user"}


@router.get("/admin/auth/me")
def admin_me(auth=Depends(admin_identity)):
    return {"username": auth[0].username, "role": "admin"}


@router.post("/auth/logout")
def logout(request: Request, response: Response, auth=Depends(bank_identity), db=Depends(database)):
    person, session = auth
    record(db, request, "LOGOUT", person.id, session)
    session.revoked = True
    session.state = "LOGGED_OUT"
    response.delete_cookie("pg_bank")
    return {"status": "logged_out"}


@router.post("/admin/auth/logout")
def admin_logout(response: Response, auth=Depends(admin_identity)):
    auth[1].revoked = True
    response.delete_cookie("pg_admin")
    return {"status": "logged_out"}
