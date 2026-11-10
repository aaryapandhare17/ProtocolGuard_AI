"""Transactional account blocking, alerts, recovery, and administrator audit."""
from dataclasses import asdict
import json
from sqlalchemy import select
from app.database.store import now
from app.fsm.engine import VERSION, step
from app.models.entities import (AdminAuditLog, BlockedEntity, DetectionResult, RiskReset,
    RiskScore, SecurityAlert, SecurityEvent, SecuritySettings, Session)
from app.security.risk import RiskPolicy, combine


def settings(db, config):
    row = db.get(SecuritySettings, 1)
    return {"threshold": row.block_threshold if row else config.block_threshold,
        "automatic_blocking": row.auto_block_enabled if row else config.auto_block_enabled}


def audit(db, action, user_id=None, admin_id=None, **evidence):
    db.add(AdminAuditLog(action=action, user_id=user_id, admin_id=admin_id,
        evidence=json.dumps(evidence, allow_nan=False)))


def serialize_alert(row):
    return {"id": row.id, "block_id": row.block_id, "user_id": row.user_id,
        "severity": row.severity, "reason": row.reason, "evidence": json.loads(row.evidence),
        "created_at": row.created_at.isoformat()+"Z",
        "resolved_at": row.resolved_at.isoformat()+"Z" if row.resolved_at else None}


def block_account(db, request, user, *, reason, source, evidence, admin_id=None):
    active = db.scalar(select(BlockedEntity).where(BlockedEntity.user_id == user.id, BlockedEntity.active.is_(True)))
    if active:
        if admin_id:
            audit(db, "ACCOUNT_BLOCK_NOOP", user.id, admin_id, block_id=active.id, note=reason)
        return active, False
    user.blocked = True
    block = BlockedEntity(user_id=user.id, source=source, reason=reason, evidence=json.dumps(evidence, allow_nan=False))
    db.add(block)
    db.flush()
    revoked = []
    for session in db.scalars(select(Session).where(Session.user_id == user.id, Session.revoked.is_(False))).all():
        transition = step(session.state, "BLOCK_ACCOUNT")
        session.state, session.revoked = transition.state_after, True
        revoked.append(session.id)
        # A control marker links the block evidence; it is not fresh threat activity.
        db.add(SecurityEvent(user_id=user.id, session_id=session.id,
            ip=request.client.host if request.client else "unknown", event_type="BLOCK_ACCOUNT",
            endpoint=request.url.path, outcome="blocked", state_before=transition.state_before,
            state_after=transition.state_after, evidence=json.dumps({"scope":"banking", "control_event":True,
                "block_id":block.id, "fsm":{"version":VERSION, **asdict(transition)}})))
    db.add(SecurityAlert(block_id=block.id, user_id=user.id, reason=reason, evidence=json.dumps(evidence, allow_nan=False)))
    audit(db, "AUTO_ACCOUNT_BLOCK" if source == "automatic" else "ACCOUNT_BLOCK", user.id, admin_id,
        block_id=block.id, note=reason, revoked_session_count=len(revoked), evidence=evidence)
    db.flush()
    return block, True


def enforce_assessment(db, request, user, detection, score):
    policy = settings(db, request.app.state.settings)
    if user.blocked or not policy["automatic_blocking"] or score <= policy["threshold"]:
        return
    block_account(db, request, user,
        reason=f"Risk score {score:.2f} exceeds configured threshold {policy['threshold']:.2f}",
        source="automatic", evidence={"event_id":detection.event_id, "detection_id":detection.id,
            "score":score, "threshold":policy["threshold"], "assessment":json.loads(detection.evidence)})


def reset_risk(db, request, user, admin_id, note):
    timestamp, previous = now(), user.risk_score
    event = SecurityEvent(user_id=user.id, ip=request.client.host if request.client else "unknown",
        event_type="ADMIN_RISK_RESET", endpoint=request.url.path, outcome="success",
        evidence=json.dumps({"scope":"admin", "admin_id":admin_id}))
    event.created_at = timestamp
    db.add(event)
    db.flush()
    payload = combine(RiskPolicy.from_settings(request.app.state.settings), fsm=0, rf=0, isolation=0, behavior=0)
    payload.update({"assessment_type":"administrative_reset", "previous_score":previous, "change":-previous,
        "reasons":["Administrator reset risk when unblocking the account"], "admin_id":admin_id, "note":note})
    detection = DetectionResult(user_id=user.id,event_id=event.id,evidence=json.dumps(payload),created_at=timestamp)
    db.add(detection)
    db.flush()
    db.add(RiskScore(user_id=user.id,detection_id=detection.id,previous_score=previous,score=0,created_at=timestamp))
    db.add(RiskReset(user_id=user.id,event_id=event.id,admin_id=admin_id,created_at=timestamp))
    user.risk_score = 0


def unblock_account(db, request, user, admin_id, note, reset):
    active = db.scalars(select(BlockedEntity).where(BlockedEntity.user_id == user.id, BlockedEntity.active.is_(True))).all()
    if not user.blocked and not active:
        audit(db,"ACCOUNT_UNBLOCK_NOOP",user.id,admin_id,note=note)
        return False
    timestamp = now()
    user.blocked = False
    for block in active:
        block.active, block.released_at = False, timestamp
        alert = db.scalar(select(SecurityAlert).where(SecurityAlert.block_id == block.id))
        if alert and alert.resolved_at is None:
            alert.resolved_at, alert.resolved_by = timestamp, admin_id
    if reset:
        reset_risk(db,request,user,admin_id,note)
    audit(db,"ACCOUNT_UNBLOCK",user.id,admin_id,note=note,reset_risk=reset,block_ids=[block.id for block in active])
    db.flush()
    return True
