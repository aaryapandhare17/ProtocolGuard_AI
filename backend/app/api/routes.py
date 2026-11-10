from datetime import timedelta
import hmac
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.database.store import now
from app.models.entities import Admin, User, Session, SecurityEvent
from app.security.credentials import digest, verify_password, hash_password
from app.services.events import record

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


def identity(request: Request, db=Depends(database), admin=False):
    cookie = "pg_admin" if admin else "pg_bank"
    raw = request.cookies.get(cookie, "")
    session = db.get(Session, digest(raw)) if raw else None
    person = db.get(Admin if admin else User, session.admin_id if admin else session.user_id) if session and (session.admin_id if admin else session.user_id) else None
    # Known blocked accounts return 403 even after their sessions were revoked.
    if not admin and person and person.blocked:
        record(db, request, "ACCESS_BLOCKED", person.id, session, "denied")
        raise HTTPException(403, "Account access restricted")
    if not session or session.revoked or session.expires_at <= now():
        record(db, request, "UNAUTHORIZED_REQUEST",
            session.user_id if session and not admin else None, session, "denied", banking=not admin)
        raise HTTPException(401, "Authentication required")
    if not person:
        raise HTTPException(403, "Role not permitted")
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
        SecurityEvent.endpoint == request.url.path,
        SecurityEvent.created_at > now() - timedelta(minutes=1)))
    if recent >= 20:
        record(db, request, "RATE_LIMIT_TRIGGERED", outcome="denied", banking=not admin)
        raise HTTPException(429, "Too many login attempts. Try again later.")
    table = Admin if admin else User
    person = db.scalar(select(table).where(table.username == data.username))
    uid = person.id if person and not admin else None
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session = Session(id=digest(token), csrf_hash=digest(csrf), user_id=uid,
        admin_id=person.id if person and admin else None,
        expires_at=now()+timedelta(hours=2), state="LOGGED_OUT")
    db.add(session)
    db.flush()
    record(db, request, "LOGIN_ATTEMPT", uid, session, banking=not admin)
    if not verify_password(data.password, person.password_hash if person else DUMMY_HASH):
        record(db, request, "LOGIN_FAILED", uid, session, "denied", banking=not admin)
        session.revoked = True
        raise HTTPException(401, "Invalid username or password")
    if not admin and person.blocked:
        record(db, request, "ACCESS_BLOCKED", uid, session, "denied")
        session.revoked = True
        raise HTTPException(403, "Account access restricted")
    record(db, request, "LOGIN_SUCCESS", uid, session, banking=not admin)
    if not admin and person.blocked:
        raise HTTPException(403, "Account access restricted")
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
    response.delete_cookie("pg_bank")
    return {"status": "logged_out"}


@router.post("/admin/auth/logout")
def admin_logout(response: Response, auth=Depends(admin_identity)):
    auth[1].revoked = True
    response.delete_cookie("pg_admin")
    return {"status": "logged_out"}


@router.get("/bank/balance")
def balance(request: Request, auth=Depends(bank_identity), db=Depends(database)):
    user, session = auth
    record(db, request, "VIEW_BALANCE", user.id, session)
    if user.blocked:
        raise HTTPException(403, "Account access restricted")
    return {"balance_cents": user.balance_cents, "currency": "INR", "username": user.username}


@router.get("/bank/history")
def history(request: Request, auth=Depends(bank_identity), db=Depends(database)):
    user, session = auth
    record(db, request, "VIEW_HISTORY", user.id, session)
    if user.blocked:
        raise HTTPException(403, "Account access restricted")
    events = db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == user.id).order_by(SecurityEvent.id.desc()).limit(30)).all()
    return [{"id": e.id, "action": e.event_type, "outcome": e.outcome, "created_at": e.created_at.isoformat()+"Z"} for e in events]


class Transfer(BaseModel):
    amount_cents: int = Field(strict=True, gt=0, le=100000000)
    recipient: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9 _-]+$")


@router.post("/bank/transfer-request")
def transfer(data: Transfer, request: Request, auth=Depends(bank_identity), db=Depends(database)):
    user, session = auth
    record(db, request, "TRANSFER_REQUEST", user.id, session)
    if user.blocked:
        raise HTTPException(403, "Account access restricted")
    record(db, request, "TRANSFER_RECORDED", user.id, session)
    if user.blocked:
        raise HTTPException(403, "Account access restricted")
    return {"status": "simulation_only", "message": "Transfer request recorded. No money was moved.", "amount_cents": data.amount_cents}
