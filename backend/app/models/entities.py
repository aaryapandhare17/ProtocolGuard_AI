from datetime import datetime
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.store import Base, now


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str]
    balance_cents: Mapped[int] = mapped_column(default=125000)
    blocked: Mapped[bool] = mapped_column(default=False)
    risk_score: Mapped[float] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)


class Admin(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str]


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    csrf_hash: Mapped[str]
    expires_at: Mapped[datetime]
    revoked: Mapped[bool] = mapped_column(default=False)
    state: Mapped[str] = mapped_column(default="AUTHENTICATED")
    created_at: Mapped[datetime] = mapped_column(default=now)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), index=True)
    ip: Mapped[str] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(index=True)
    endpoint: Mapped[str]
    outcome: Mapped[str]
    simulated: Mapped[bool] = mapped_column(default=False)
    state_before: Mapped[str] = mapped_column(default="LOGGED_OUT")
    state_after: Mapped[str] = mapped_column(default="LOGGED_OUT")
    evidence: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)
