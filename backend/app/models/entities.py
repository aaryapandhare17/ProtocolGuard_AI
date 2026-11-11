from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, Index, text, UniqueConstraint
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


class DetectionResult(Base):
    __tablename__ = "detection_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("security_events.id"), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    detection_id: Mapped[int] = mapped_column(ForeignKey("detection_results.id"), unique=True)
    previous_score: Mapped[float]
    score: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)


class SecuritySettings(Base):
    __tablename__ = "security_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    block_threshold: Mapped[float] = mapped_column(default=60)
    auto_block_enabled: Mapped[bool] = mapped_column(default=True)


class BlockedEntity(Base):
    __tablename__ = "blocked_entities"
    __table_args__ = (Index("uq_active_account_block", "user_id", unique=True, sqlite_where=text("active = 1")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(default="account")
    active: Mapped[bool] = mapped_column(default=True, index=True)
    source: Mapped[str]
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)
    released_at: Mapped[datetime | None]


class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("blocked_entities.id"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    severity: Mapped[str] = mapped_column(default="high")
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now, index=True)
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str]
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)


class RiskReset(Base):
    __tablename__ = "risk_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("security_events.id"), unique=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(default=now)


class SuspiciousIP(Base):
    __tablename__ = "suspicious_ips"
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(45),unique=True,index=True)
    first_seen: Mapped[datetime] = mapped_column(default=now)
    last_seen: Mapped[datetime] = mapped_column(default=now)
    suspicious_count: Mapped[int] = mapped_column(default=0)
    risk_score: Mapped[float] = mapped_column(default=0)
    reset_event_id: Mapped[int] = mapped_column(default=0)


class IPAccount(Base):
    __tablename__ = "ip_accounts"
    __table_args__ = (UniqueConstraint("ip_id","user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ip_id: Mapped[int] = mapped_column(ForeignKey("suspicious_ips.id"),index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),index=True)
    first_seen: Mapped[datetime] = mapped_column(default=now)
    last_seen: Mapped[datetime] = mapped_column(default=now)


class IPRestriction(Base):
    __tablename__ = "ip_restrictions"
    __table_args__ = (Index("uq_active_ip_restriction","ip_id",unique=True,sqlite_where=text("active = 1")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ip_id: Mapped[int] = mapped_column(ForeignKey("suspicious_ips.id"),index=True)
    active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str]
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)
    expires_at: Mapped[datetime | None]
    released_at: Mapped[datetime | None]


class IPSecurityAlert(Base):
    __tablename__ = "ip_security_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip_id: Mapped[int] = mapped_column(ForeignKey("suspicious_ips.id"),index=True)
    restriction_id: Mapped[int] = mapped_column(ForeignKey("ip_restrictions.id"),unique=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)
    resolved_at: Mapped[datetime | None]


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[str] = mapped_column(String(32),primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"),index=True)
    scenario: Mapped[str]
    status: Mapped[str] = mapped_column(default="running",index=True)
    configuration: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text,default="{}")
    started_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[datetime | None]
