"""Find persisted DFA checkpoints referenced by alert evidence."""

import json

from sqlalchemy import select

from app.fsm.engine import VERSION
from app.models.entities import SecurityEvent


def attach_alert_replays(db, alerts):
    event_ids = {
        alert["evidence"].get("event_id")
        for alert in alerts
        if type(alert["evidence"].get("event_id")) is int
    }
    if not event_ids:
        return alerts
    events = db.scalars(
        select(SecurityEvent).where(
            SecurityEvent.id.in_(event_ids), SecurityEvent.session_id.is_not(None)
        )
    )
    replay_by_id = {
        event.id: {"session_id": event.session_id, "event_id": event.id}
        for event in events
        if json.loads(event.evidence).get("fsm", {}).get("version") == VERSION
    }
    for alert in alerts:
        event_id = alert["evidence"].get("event_id")
        if type(event_id) is int and event_id in replay_by_id:
            alert["replay"] = replay_by_id[event_id]
    return alerts
