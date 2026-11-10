"""Persist the event and its DFA evidence in the caller's transaction."""
import json
from dataclasses import asdict
from app.fsm.engine import VERSION, step
from app.models.entities import SecurityEvent
from app.services.risk import assess_event
from app.services.ips import observe_event


def record(db, request, kind, user_id=None, session=None, outcome="success", *, banking=True):
    before = session.state if session else "LOGGED_OUT"
    after = before
    metadata = {"scope": "banking" if banking else "admin"}
    if banking:
        transition = step(before, kind)
        after = transition.state_after
        metadata["fsm"] = {"version": VERSION, **asdict(transition)}
        if session:
            session.state = after
    row = SecurityEvent(user_id=user_id, session_id=session.id if session else None,
        ip=request.client.host if request.client else "unknown", event_type=kind,
        endpoint=request.url.path, outcome=outcome, state_before=before,
        state_after=after, evidence=json.dumps(metadata))
    db.add(row)
    db.flush()
    if banking:
        assess_event(db, request, row, transition)
    observe_event(db, request, row)
    return row
