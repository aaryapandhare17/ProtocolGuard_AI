import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.api.routes import admin_identity, database
from app.fsm.engine import VERSION, definition, evaluate
from app.models.entities import SecurityEvent, Session, User

router = APIRouter(prefix="/api/admin/fsm", dependencies=[Depends(admin_identity)])


@router.get("")
def get_definition():
    return definition()


@router.get("/sessions")
def sessions(db=Depends(database)):
    # Only sessions with supported banking evidence are offered for replay.
    rows = db.execute(
        select(SecurityEvent, User.username)
        .outerjoin(User, SecurityEvent.user_id == User.id)
        .order_by(SecurityEvent.id.desc())
    ).yield_per(200)
    seen, result = set(), []
    for row, username in rows:
        evidence = json.loads(row.evidence)
        if (
            not row.session_id
            or row.session_id in seen
            or evidence.get("fsm", {}).get("version") != VERSION
        ):
            continue
        seen.add(row.session_id)
        result.append(
            {
                "session_id": row.session_id,
                "user_id": row.user_id,
                "username": username,
                "state": row.state_after,
                "last_event_at": row.created_at.isoformat() + "Z",
            }
        )
        if len(result) == 100:
            break
    return result


@router.get("/sessions/{session_id}")
def replay(session_id: str, db=Depends(database)):
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    rows = db.scalars(
        select(SecurityEvent)
        .where(SecurityEvent.session_id == session_id)
        .order_by(SecurityEvent.id)
    ).all()
    supported = [
        row
        for row in rows
        if json.loads(row.evidence).get("fsm", {}).get("version") == VERSION
    ]
    if not supported:
        raise HTTPException(404, "No banking DFA evidence for this session")
    initial = supported[0].state_before
    report = evaluate([row.event_type for row in supported], initial_state=initial)
    report["session_id"] = session_id
    report["user_id"] = session.user_id
    report["complete_trace"] = (
        len(supported) == len(rows)
        and initial == "LOGGED_OUT"
        and supported[0].event_type == "LOGIN_ATTEMPT"
    )
    # Legacy prefixes are not upgraded or invented. CLOSED applies only to the
    # analyzed suffix when complete_trace is false.
    report["persisted_events"] = [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() + "Z",
            "outcome": row.outcome,
            "state_before": row.state_before,
            "state_after": row.state_after,
            "evidence": json.loads(row.evidence)["fsm"],
        }
        for row in supported
    ]
    return report
