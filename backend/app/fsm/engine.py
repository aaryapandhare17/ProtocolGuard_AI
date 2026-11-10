"""Pure, deterministic banking-session DFA; never an authorization mechanism."""
from dataclasses import asdict, dataclass
from typing import Iterable

VERSION = "bank-session-v1"
STATES = (
    "LOGGED_OUT", "AUTHENTICATING", "AUTHENTICATED", "VIEWING_ACCOUNT",
    "TRANSFER_PENDING", "CLOSED", "BLOCKED", "REJECTED",
)
ALPHABET = (
    "LOGIN_ATTEMPT", "LOGIN_SUCCESS", "LOGIN_FAILED", "VIEW_BALANCE", "VIEW_HISTORY",
    "TRANSFER_REQUEST", "TRANSFER_RECORDED", "RETURN", "CANCEL_TRANSFER", "LOGOUT",
    "UNAUTHORIZED_REQUEST", "RATE_LIMIT_TRIGGERED", "ACCESS_BLOCKED", "BLOCK_ACCOUNT",
)
INITIAL_STATE = "LOGGED_OUT"
ACCEPTING_STATES = frozenset({"CLOSED"})
LIVE_STATES = frozenset({"AUTHENTICATED", "VIEWING_ACCOUNT", "TRANSFER_PENDING"})
TRANSITIONS = {
    ("LOGGED_OUT", "LOGIN_ATTEMPT"): "AUTHENTICATING",
    ("AUTHENTICATING", "LOGIN_SUCCESS"): "AUTHENTICATED",
    ("AUTHENTICATING", "LOGIN_FAILED"): "LOGGED_OUT",
    ("AUTHENTICATING", "ACCESS_BLOCKED"): "BLOCKED",
    ("VIEWING_ACCOUNT", "RETURN"): "AUTHENTICATED",
    ("TRANSFER_PENDING", "TRANSFER_RECORDED"): "AUTHENTICATED",
    ("TRANSFER_PENDING", "CANCEL_TRANSFER"): "AUTHENTICATED",
    ("BLOCKED", "ACCESS_BLOCKED"): "BLOCKED",
}
for state in ("AUTHENTICATED", "VIEWING_ACCOUNT"):
    for event in ("VIEW_BALANCE", "VIEW_HISTORY"):
        TRANSITIONS[state, event] = "VIEWING_ACCOUNT"
    TRANSITIONS[state, "TRANSFER_REQUEST"] = "TRANSFER_PENDING"
for state in LIVE_STATES:
    TRANSITIONS[state, "LOGOUT"] = "CLOSED"
for state in STATES:
    if state not in {"CLOSED", "REJECTED"}:
        TRANSITIONS[state, "BLOCK_ACCOUNT"] = "BLOCKED"
        TRANSITIONS[state, "ACCESS_BLOCKED"] = "BLOCKED"


@dataclass(frozen=True)
class Transition:
    state_before: str
    event: str
    state_after: str
    valid: bool
    violation: str | None


def step(state: str, event: str) -> Transition:
    if state not in STATES:
        raise ValueError(f"Unknown DFA state: {state}")
    if event not in ALPHABET:
        return Transition(state, event, "REJECTED", False, f"Unknown event {event!r}; outside the event alphabet.")
    target = TRANSITIONS.get((state, event))
    if target is None:
        reason = ("Sequence already rejected; subsequent activity cannot erase its violation."
            if state == "REJECTED" else f"{event} is not permitted from {state}.")
        return Transition(state, event, "REJECTED", False, reason)
    return Transition(state, event, target, True, None)


def evaluate(events: Iterable[str], initial_state: str = INITIAL_STATE) -> dict:
    if initial_state not in STATES:
        raise ValueError(f"Unknown DFA state: {initial_state}")
    state = initial_state
    transitions = []
    for event in events:
        transition = step(state, event)
        transitions.append(asdict(transition))
        state = transition.state_after
    violations = [dict(index=i, explanation=t["violation"]) for i, t in enumerate(transitions) if not t["valid"]]
    accepted = state in ACCEPTING_STATES and not violations
    # CLOSED cannot be reached from BLOCKED or REJECTED. A blocked sequence is not
    # a benign valid prefix, even when its enforcement transitions are defined.
    valid_prefix = not violations and state not in {"BLOCKED", "REJECTED"}
    return {
        "version": VERSION, "initial_state": initial_state,
        "events": [t["event"] for t in transitions], "transitions": transitions,
        "invalid_transition_count": len(violations), "violations": violations,
        "final_state": state, "accepted": accepted, "valid_prefix": valid_prefix,
        "suspicious": bool(violations) or state == "BLOCKED",
        "classification": "accepted" if accepted else "suspicious" if violations or state == "BLOCKED" else "valid_prefix",
    }


def definition() -> dict:
    return {
        "version": VERSION, "states": list(STATES), "alphabet": list(ALPHABET),
        "initial_state": INITIAL_STATE, "accepting_states": sorted(ACCEPTING_STATES),
        "rejecting_state": "REJECTED",
        "transitions": [
            {"from": state, "event": event, "to": step(state, event).state_after,
             "explicit": (state, event) in TRANSITIONS}
            for state in STATES for event in ALPHABET
        ],
    }
