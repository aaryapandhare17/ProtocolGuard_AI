"""One feature contract for synthetic training data and live event inference."""
from dataclasses import dataclass
import math
from typing import Iterable
from app.fsm.engine import ALPHABET, INITIAL_STATE, STATES, VERSION as FSM_VERSION, step

FEATURE_VERSION = "bank-features-v1"
BASE_FEATURES = (
    "event_count", "login_failure_count", "transfer_attempt_count",
    "invalid_transition_count", "invalid_transition_rate", "session_duration_seconds",
    "request_frequency", "average_inter_event_seconds", "minimum_inter_event_seconds",
    "short_interval_ratio", "distinct_endpoint_count", "unknown_event_count",
)
FEATURE_NAMES = BASE_FEATURES + tuple(f"event_fraction:{event}" for event in ALPHABET) + tuple(
    f"transition_fraction:{source}:{target}" for source in STATES for target in STATES)


@dataclass(frozen=True)
class ActivityEvent:
    event_type: str
    timestamp: float
    endpoint: str

    def __post_init__(self):
        if not isinstance(self.event_type, str) or not self.event_type:
            raise ValueError("Event type must be a nonempty string")
        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, (int, float)) or not math.isfinite(self.timestamp):
            raise ValueError("Timestamp must be finite epoch seconds")
        if not isinstance(self.endpoint, str) or not self.endpoint.startswith("/"):
            raise ValueError("Endpoint must be an absolute API path")


def extract_features(events: Iterable[ActivityEvent], initial_state: str = INITIAL_STATE) -> dict[str, float]:
    events = tuple(events)
    if initial_state not in STATES:
        raise ValueError("Unknown initial DFA state")
    intervals = [right.timestamp-left.timestamp for left, right in zip(events, events[1:])]
    if any(gap < 0 for gap in intervals):
        raise ValueError("Events must be ordered by timestamp")
    count = len(events)
    duration = events[-1].timestamp-events[0].timestamp if count > 1 else 0.0
    state, invalid = initial_state, 0
    event_counts = dict.fromkeys(ALPHABET, 0)
    transitions = {(source, target): 0 for source in STATES for target in STATES}
    for event in events:
        result = step(state, event.event_type)
        invalid += not result.valid
        transitions[state, result.state_after] += 1
        state = result.state_after
        if event.event_type in event_counts:
            event_counts[event.event_type] += 1
    values = [
        count, event_counts["LOGIN_FAILED"], event_counts["TRANSFER_REQUEST"], invalid,
        invalid/max(count, 1), duration, max(count-1, 0)/max(duration, 1.0),
        sum(intervals)/max(len(intervals), 1), min(intervals, default=0.0),
        sum(gap < 0.25 for gap in intervals)/max(len(intervals), 1),
        len({e.endpoint for e in events}), sum(e.event_type not in ALPHABET for e in events),
    ]
    values += [event_counts[event]/max(count, 1) for event in ALPHABET]
    values += [transitions[source, target]/max(count, 1) for source in STATES for target in STATES]
    return dict(zip(FEATURE_NAMES, map(float, values), strict=True))


def feature_vector(events: Iterable[ActivityEvent], initial_state: str = INITIAL_STATE) -> list[float]:
    features = extract_features(events, initial_state)
    return [features[name] for name in FEATURE_NAMES]


def from_security_events(rows) -> tuple[ActivityEvent, ...]:
    """Adapt timestamp-ordered SQLAlchemy records; naive DB timestamps are UTC."""
    from datetime import timezone
    return tuple(ActivityEvent(row.event_type,
        row.created_at.replace(tzinfo=timezone.utc).timestamp() if row.created_at.tzinfo is None else row.created_at.timestamp(),
        row.endpoint) for row in rows)


def feature_schema() -> dict:
    return {"version": FEATURE_VERSION, "fsm_version": FSM_VERSION, "feature_names": list(FEATURE_NAMES)}
