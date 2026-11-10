"""Public-to-administrator projections; never serialize ORM credentials or tokens."""

import json
from sqlalchemy import select
from app.models.entities import Admin, DetectionResult, SecurityEvent, Session, User


def serialize_event(event, username=None, detection=None, admin_username=None):
    metadata = json.loads(event.evidence)
    assessment = json.loads(detection.evidence) if detection else {}
    score = assessment.get("score")
    return {
        "id": event.id,
        "user_id": event.user_id,
        "username": username or admin_username,
        "account_type": "bank"
        if event.user_id
        else "admin"
        if admin_username
        else "unattributed",
        "session_id": event.session_id,
        "ip": event.ip,
        "event_type": event.event_type,
        "created_at": event.created_at.isoformat() + "Z",
        "endpoint": event.endpoint,
        "outcome": event.outcome,
        "state_before": event.state_before,
        "state_after": event.state_after,
        "simulated": event.simulated,
        "scope": metadata.get("scope", "legacy"),
        "fsm": metadata.get("fsm"),
        "risk_score": score,
        "ml_status": assessment.get("ml", {}).get("status", "unassessed"),
        "detection_status": assessment.get("level", "unassessed"),
    }


def event_query():
    return (
        select(SecurityEvent, User.username, DetectionResult, Admin.username)
        .outerjoin(User, SecurityEvent.user_id == User.id)
        .outerjoin(DetectionResult, DetectionResult.event_id == SecurityEvent.id)
        .outerjoin(Session, SecurityEvent.session_id == Session.id)
        .outerjoin(Admin, Session.admin_id == Admin.id)
    )


def event_batch(db, *, after_id=0, limit=100):
    rows = db.execute(
        event_query()
        .where(SecurityEvent.id > after_id)
        .order_by(SecurityEvent.id)
        .limit(limit)
    ).all()
    return [serialize_event(*row) for row in rows]
