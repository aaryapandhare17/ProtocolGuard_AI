"""Pure, transparent hybrid scoring; scores are indices, not probabilities."""
from dataclasses import asdict, dataclass
import math

POLICY_VERSION = "hybrid-risk-v1"


@dataclass(frozen=True)
class RiskPolicy:
    fsm_weight: float = .30
    rf_weight: float = .35
    if_weight: float = .10
    behavior_weight: float = .25
    window_seconds: int = 60
    half_life_seconds: int = 600
    max_events: int = 200

    def __post_init__(self):
        weights = [self.fsm_weight, self.rf_weight, self.if_weight, self.behavior_weight]
        if not all(math.isfinite(w) and 0 <= w <= 1 for w in weights) or not math.isclose(sum(weights), 1, abs_tol=1e-9):
            raise ValueError("Weights must be finite, bounded, and sum to one")
        if self.window_seconds <= 0 or self.half_life_seconds <= 0 or self.max_events <= 0:
            raise ValueError("Observation and decay parameters must be positive")

    @classmethod
    def from_settings(cls, settings):
        return cls(settings.risk_fsm_weight, settings.risk_rf_weight, settings.risk_if_weight,
            settings.risk_behavior_weight, settings.risk_window_seconds,
            settings.risk_half_life_seconds, settings.risk_max_events)

    def describe(self):
        return {"version": POLICY_VERSION, **asdict(self)}


def decay(score, elapsed_seconds, half_life_seconds):
    if not all(math.isfinite(value) for value in (score, elapsed_seconds, half_life_seconds)) or half_life_seconds <= 0:
        raise ValueError("Invalid decay parameters")
    return min(100.0, max(0.0, score))*2**(-max(elapsed_seconds, 0)/half_life_seconds)


def combine(policy, *, fsm, rf, isolation, behavior, previous_score=0, elapsed_seconds=0):
    units = {"fsm": fsm, "random_forest": rf, "isolation_forest": isolation, "behavior": behavior}
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in units.values()):
        raise ValueError("Evidence components must be finite values in [0,1]")
    weights = {"fsm": policy.fsm_weight, "random_forest": policy.rf_weight,
        "isolation_forest": policy.if_weight, "behavior": policy.behavior_weight}
    contributions = {name: 100*units[name]*weights[name] for name in units}
    assessment = min(100.0, sum(contributions.values()))
    retained = decay(previous_score, elapsed_seconds, policy.half_life_seconds)
    score = min(100.0, max(assessment, retained))
    return {"policy": policy.describe(), "components": units, "contributions": contributions,
        "assessment_score": assessment, "previous_score": previous_score, "decayed_previous_score": retained,
        "score": score, "change": score-previous_score,
        "level": "low" if score < 30 else "monitoring" if score <= 60 else "high",
        "score_note": "Risk index, not a probability of malicious behavior; evidence is not added repeatedly."}


REQUEST_EVENTS = frozenset({"LOGIN_ATTEMPT", "VIEW_BALANCE", "VIEW_HISTORY", "TRANSFER_REQUEST",
    "LOGOUT", "UNAUTHORIZED_REQUEST", "RATE_LIMIT_TRIGGERED", "ACCESS_BLOCKED"})


def behavioral_evidence(rows):
    failures = sum(row.event_type == "LOGIN_FAILED" for row in rows)
    transfers = sum(row.event_type == "TRANSFER_REQUEST" for row in rows)
    unauthorized = sum(row.event_type == "UNAUTHORIZED_REQUEST" for row in rows)
    requests = sum(row.event_type in REQUEST_EVENTS for row in rows)
    duration = (rows[-1].created_at-rows[0].created_at).total_seconds() if len(rows) > 1 else 0
    rate = requests/max(duration, 1)
    factors = {
        "failed_logins": min(1, max(0, failures-2)/6),
        "transfer_requests": min(1, max(0, transfers-3)/12),
        "unauthorized_requests": min(1, unauthorized/3),
        "request_burst": min(1, max(0, rate-5)/20) if requests >= 10 else 0,
        "rate_limit": float(any(row.event_type == "RATE_LIMIT_TRIGGERED" for row in rows)),
    }
    return {"value": max(factors.values()), "factors": factors,
        "counts": {"failed_logins": failures, "transfer_requests": transfers,
            "unauthorized_requests": unauthorized, "requests": requests}, "request_rate": rate}
