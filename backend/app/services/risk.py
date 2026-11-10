"""Persist per-event detection evidence and per-user decaying risk snapshots."""
from datetime import timedelta
import json
import logging
import math
from pathlib import Path
from sqlalchemy import select
from app.database.store import now
from app.ml.features import from_security_events
from app.models.entities import DetectionResult, RiskScore, RiskReset, SecurityEvent, Session, User
from app.security.risk import RiskPolicy, behavioral_evidence, combine, decay

logger = logging.getLogger(__name__)


def load_detector(settings):
    if not settings.ml_enabled:
        return None, "disabled"
    if not (Path(settings.ml_model_directory)/"artifact-manifest.json").exists():
        return None, "artifacts_missing"
    try:
        json.loads((Path(settings.ml_model_directory)/"artifact-manifest.json").read_text())
        from app.ml.inference import DetectorBundle
        return DetectorBundle.load(settings.ml_model_directory), "ready"
    except ImportError:
        return None, "dependencies_missing"
    except Exception as error:
        logger.warning("ML artifacts unavailable (%s)", type(error).__name__)
        return None, "artifacts_invalid"


def model_evidence(db, app, row, recent, policy):
    detector = app.state.detector
    if detector is None:
        return {"status": app.state.ml_status, "predictions": [], "failures": []}, 0.0, 0.0
    candidates, skipped = [], []
    if row.session_id:
        rows = list(reversed(db.scalars(select(SecurityEvent).where(
            SecurityEvent.session_id == row.session_id).order_by(SecurityEvent.id.desc()).limit(policy.max_events+1)).all()))
        session = db.get(Session, row.session_id)
        if session and session.revoked:
            skipped.append("session_revoked")
        elif len(rows) > policy.max_events:
            skipped.append("session_event_limit")
        elif len(rows) < 4:
            skipped.append("session_too_short")
        elif rows[0].event_type != "LOGIN_ATTEMPT" or rows[0].state_before != "LOGGED_OUT":
            skipped.append("session_missing_initial_prefix")
        else:
            candidates.append(("session", rows))
    failed_sessions = {event.session_id for event in recent if event.event_type == "LOGIN_FAILED" and event.session_id}
    if len(failed_sessions) >= 3:
        rows = db.scalars(select(SecurityEvent).where(SecurityEvent.session_id.in_(failed_sessions),
            SecurityEvent.event_type.in_(["LOGIN_ATTEMPT", "LOGIN_FAILED"])).order_by(SecurityEvent.id).limit(policy.max_events+1)).all()
        if len(rows) <= policy.max_events and len(rows) == 2*len(failed_sessions):
            candidates.append(("failed_login_window", rows))
        else:
            skipped.append("failed_login_window_incomplete")
    predictions, failures = [], []
    for context, rows in candidates:
        try:
            result = detector.predict(from_security_events(rows), complete=rows[-1].event_type == "LOGOUT")
            values = (result["random_forest"]["score"], result["isolation_forest"]["anomaly_evidence"])
            if not all(math.isfinite(value) and 0 <= value <= 1 for value in values):
                raise ValueError("Invalid model evidence")
            predictions.append({"context": context, "event_ids": [event.id for event in rows], "prediction": result})
        except Exception as error:
            logger.warning("ML inference unavailable (%s)", type(error).__name__)
            failures.append({"context": context, "reason": type(error).__name__})
    rf = max((result["prediction"]["random_forest"]["score"] for result in predictions), default=0.0)
    isolation = max((result["prediction"]["isolation_forest"]["anomaly_evidence"] for result in predictions), default=0.0)
    return {"status": "inference_failed" if failures else "ready" if predictions else "insufficient_observation",
        "predictions": predictions, "failures": failures, "skipped": skipped}, rf, isolation


def assess_event(db, request, row, fsm_transition):
    policy = RiskPolicy.from_settings(request.app.state.settings)
    user = db.get(User, row.user_id) if row.user_id else None
    cutoff = row.created_at-timedelta(seconds=policy.window_seconds)
    reset = db.scalar(select(RiskReset).where(RiskReset.user_id == user.id).order_by(RiskReset.id.desc()).limit(1)) if user else None
    recent = list(reversed(db.scalars(select(SecurityEvent).where(
        SecurityEvent.user_id == user.id, SecurityEvent.created_at >= cutoff,
        SecurityEvent.id > (reset.event_id if reset else 0), SecurityEvent.event_type != "BLOCK_ACCOUNT")
        .order_by(SecurityEvent.id.desc()).limit(policy.max_events+1)).all())) if user else [row]
    truncated = len(recent) > policy.max_events
    recent = recent[-policy.max_events:]
    behavior = behavioral_evidence(recent)
    if user:
        ml, rf, isolation = model_evidence(db, request.app, row, recent, policy)
        prior = db.scalar(select(RiskScore).where(RiskScore.user_id == user.id).order_by(RiskScore.id.desc()).limit(1))
        previous = user.risk_score
        elapsed = (row.created_at-prior.created_at).total_seconds() if prior else 0
    else:
        ml, rf, isolation = {"status": "no_identified_user", "predictions": [], "failures": []}, 0.0, 0.0
        previous, elapsed = 0, 0
    fsm = float(not fsm_transition.valid or fsm_transition.state_after == "BLOCKED")
    result = combine(policy, fsm=fsm, rf=rf, isolation=isolation, behavior=behavior["value"],
        previous_score=previous, elapsed_seconds=elapsed)
    reasons = [f"{name} contributed {value:.2f} points" for name, value in result["contributions"].items() if value > 0]
    if result["decayed_previous_score"] > result["assessment_score"]:
        reasons.append("Retained previous risk after time-based decay")
    if not reasons:
        reasons.append("No positive risk evidence in this assessment")
    payload = {**result, "reasons": reasons, "ml": ml, "behavior": behavior,
        "fsm": {"valid": fsm_transition.valid, "violation": fsm_transition.violation},
        "window": {"seconds": policy.window_seconds, "event_ids": [event.id for event in recent], "truncated": truncated},
        "scope": "user" if user else "unattributed_event", "ip_risk_included": False,
        "ml_weights_renormalized": False}
    detection = DetectionResult(event_id=row.id, user_id=row.user_id, evidence=json.dumps(payload, allow_nan=False), created_at=row.created_at)
    db.add(detection)
    db.flush()
    if user:
        user.risk_score = result["score"]
        db.add(RiskScore(user_id=user.id, detection_id=detection.id, previous_score=previous,
            score=result["score"], created_at=row.created_at))
        db.flush()
        from app.services.blocking import enforce_assessment
        enforce_assessment(db, request, user, detection, result["score"])
    return detection


def current_risk(db, user, policy, at=None):
    latest = db.scalar(select(RiskScore).where(RiskScore.user_id == user.id).order_by(RiskScore.id.desc()).limit(1))
    elapsed = ((at or now())-latest.created_at).total_seconds() if latest else 0
    score = decay(user.risk_score, elapsed, policy.half_life_seconds)
    return {"user_id": user.id, "username": user.username, "stored_score": user.risk_score,
        "effective_score": score, "last_assessed_at": latest.created_at.isoformat()+"Z" if latest else None,
        "level": "low" if score < 30 else "monitoring" if score <= 60 else "high"}
