"""Read-only dashboard data from persisted banking/security activity."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, or_
from app.api.routes import admin_identity, database
from app.database.store import now
from app.models.entities import (
    DetectionResult,
    IPAccount,
    IPRestriction,
    IPSecurityAlert,
    SecurityAlert,
    SecurityEvent,
    Session,
    SuspiciousIP,
    User,
)
from app.security.risk import RiskPolicy
from app.services.risk import current_risk
from app.services.admin_views import event_query, serialize_event
from app.services.blocking import serialize_alert
from app.services.ips import serialize_alert as serialize_ip_alert

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_identity)])


def user_summary(db, user, config):
    return {
        **current_risk(db, user, RiskPolicy.from_settings(config)),
        "id": user.id,
        "blocked": user.blocked,
        "created_at": user.created_at.isoformat() + "Z",
    }


@router.get("/overview")
def overview(request: Request, db=Depends(database)):
    timestamp = now()
    users = db.scalars(select(User).order_by(User.id)).all()
    summaries = [user_summary(db, user, request.app.state.settings) for user in users]
    count = lambda model, *conditions: (
        db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
    )
    accounts = db.scalars(
        select(SecurityAlert).order_by(SecurityAlert.id.desc()).limit(5)
    ).all()
    ips = db.scalars(
        select(IPSecurityAlert).order_by(IPSecurityAlert.id.desc()).limit(5)
    ).all()
    incidents = [
        {
            **serialize_alert(row),
            "entity_type": "account",
            "target": next(
                (u.username for u in users if u.id == row.user_id),
                f"User {row.user_id}",
            ),
        }
        for row in accounts
    ]
    incidents += [
        {
            **serialize_ip_alert(db, row),
            "entity_type": "ip",
            "target": db.get(SuspiciousIP, row.ip_id).address,
        }
        for row in ips
    ]
    incidents.sort(key=lambda item: item["created_at"], reverse=True)
    hour = timestamp.replace(minute=0, second=0, microsecond=0)
    buckets = {hour - timedelta(hours=index): 0 for index in reversed(range(24))}
    for created in db.scalars(
        select(SecurityEvent.created_at).where(
            SecurityEvent.created_at >= hour - timedelta(hours=23)
        )
    ):
        key = created.replace(minute=0, second=0, microsecond=0)
        if key in buckets:
            buckets[key] += 1
    return {
        "total_users": len(users),
        "active_sessions": count(
            Session,
            Session.user_id.is_not(None),
            Session.revoked.is_(False),
            Session.expires_at > timestamp,
        ),
        "events_analyzed": db.scalar(
            select(func.count())
            .select_from(DetectionResult)
            .join(SecurityEvent, DetectionResult.event_id == SecurityEvent.id)
            .where(SecurityEvent.event_type != "ADMIN_RISK_RESET")
        )
        or 0,
        "suspicious_users": sum(user["effective_score"] >= 30 for user in summaries),
        "blocked_accounts": sum(user.blocked for user in users),
        "blocked_ips": count(
            IPRestriction,
            IPRestriction.active.is_(True),
            or_(
                IPRestriction.expires_at.is_(None), IPRestriction.expires_at > timestamp
            ),
        ),
        "alerts_24h": count(
            SecurityAlert, SecurityAlert.created_at >= timestamp - timedelta(hours=24)
        )
        + count(
            IPSecurityAlert,
            IPSecurityAlert.created_at >= timestamp - timedelta(hours=24),
        ),
        "threat_distribution": [
            {"level": level, "count": sum(user["level"] == level for user in summaries)}
            for level in ("low", "monitoring", "high")
        ],
        "activity": [
            {"timestamp": key.isoformat() + "Z", "count": value}
            for key, value in buckets.items()
        ],
        "recent_incidents": incidents[:5],
        "ml_status": request.app.state.ml_status,
        "event_cursor": db.scalar(select(func.max(SecurityEvent.id))) or 0,
    }


@router.get("/users")
def users(
    request: Request,
    q: str = Query("", max_length=80),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db=Depends(database),
):
    conditions = [User.username.contains(q, autoescape=True)] if q else []
    rows = db.scalars(
        select(User).where(*conditions).order_by(User.id).offset(offset).limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    return {
        "items": [user_summary(db, row, request.app.state.settings) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/users/{user_id}")
def user(user_id: int, request: Request, db=Depends(database)):
    person = db.get(User, user_id)
    if not person:
        raise HTTPException(404, "User not found")
    ips = db.execute(
        select(SuspiciousIP.id, SuspiciousIP.address)
        .join(IPAccount, IPAccount.ip_id == SuspiciousIP.id)
        .where(IPAccount.user_id == user_id)
    ).all()
    events = db.execute(
        event_query()
        .where(SecurityEvent.user_id == user_id)
        .order_by(SecurityEvent.id.desc())
        .limit(100)
    ).all()
    return {
        **user_summary(db, person, request.app.state.settings),
        "associated_ips": [{"id": row.id, "address": row.address} for row in ips],
        "events": [serialize_event(*row) for row in events],
    }


@router.get("/events")
def events(
    q: str = Query("", max_length=80),
    user_id: int | None = None,
    after_id: int = Query(0, ge=0),
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=200),
    db=Depends(database),
):
    query = event_query().where(SecurityEvent.id > after_id)
    if user_id is not None:
        query = query.where(SecurityEvent.user_id == user_id)
    if before_id is not None:
        query = query.where(SecurityEvent.id < before_id)
    if q:
        query = query.where(
            or_(
                User.username.contains(q, autoescape=True),
                SecurityEvent.ip.contains(q, autoescape=True),
                SecurityEvent.event_type.contains(q, autoescape=True),
            )
        )
    return [
        serialize_event(*row)
        for row in db.execute(query.order_by(SecurityEvent.id.desc()).limit(limit))
    ]
