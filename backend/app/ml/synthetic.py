"""Local, reproducible activity synthesis; performs no network requests."""

from dataclasses import asdict, dataclass
import random
from app.ml.features import ActivityEvent

GENERATOR_VERSION = "bank-synthetic-v2"
RECIPE_COUNT = 20
SCENARIOS = {
    "normal_browsing": (0, 24),
    "normal_transfer": (0, 16),
    "normal_busy": (0, 6),
    "normal_retry": (0, 12),
    "failed_login_burst": (1, 6),
    "failed_login_paced": (1, 12),
    "unauthorized_access": (1, 8),
    "rapid_requests": (1, 8),
    "transfer_burst": (1, 8),
    "invalid_sequence": (1, 6),
    "heldout_slow_normal": (0, 4),
    "heldout_paced_transfer": (1, 4),
    "heldout_jittered_login_failures": (1, 4),
    "heldout_delayed_retry": (0, 4),
}
HELDOUT_SCENARIOS = frozenset(
    {
        "heldout_slow_normal",
        "heldout_paced_transfer",
        "heldout_jittered_login_failures",
        "heldout_delayed_retry",
    }
)
ENDPOINTS = {
    "LOGIN_ATTEMPT": "/api/auth/login",
    "LOGIN_SUCCESS": "/api/auth/login",
    "LOGIN_FAILED": "/api/auth/login",
    "VIEW_BALANCE": "/api/bank/balance",
    "VIEW_HISTORY": "/api/bank/history",
    "TRANSFER_REQUEST": "/api/bank/transfer-request",
    "TRANSFER_RECORDED": "/api/bank/transfer-request",
    "LOGOUT": "/api/auth/logout",
    "RETURN": "/api/bank/return",
    "UNAUTHORIZED_REQUEST": "/api/bank/balance",
}


@dataclass(frozen=True)
class SyntheticSession:
    session_id: str
    scenario: str
    group_id: str
    split: str
    label: int
    events: tuple[ActivityEvent, ...]

    def to_dict(self):
        return asdict(self)


def split_recipes(seed: int) -> dict[tuple[str, int], str]:
    """Group all repetitions of one scenario recipe in one partition."""
    assignments = {}
    for scenario in sorted(SCENARIOS):
        recipes = list(range(RECIPE_COUNT))
        random.Random(f"{seed}:split:{scenario}").shuffle(recipes)
        for index, recipe in enumerate(recipes):
            assignments[scenario, recipe] = (
                "held_out"
                if scenario in HELDOUT_SCENARIOS
                else "train"
                if index < 14
                else "validation"
                if index < 17
                else "test"
            )
    return assignments


def make_events(
    scenario: str, recipe: int, rng: random.Random, start: float
) -> tuple[ActivityEvent, ...]:
    if scenario not in SCENARIOS or not 0 <= recipe < RECIPE_COUNT:
        raise ValueError("Unknown scenario or recipe")
    types = []
    if scenario in {
        "failed_login_burst",
        "failed_login_paced",
        "heldout_jittered_login_failures",
    }:
        failures = (
            6 + recipe
            if scenario == "failed_login_burst"
            else 8 + recipe % 12
            if scenario == "failed_login_paced"
            else 15 + recipe % 4
        )
        types = [
            event
            for _ in range(failures)
            for event in ("LOGIN_ATTEMPT", "LOGIN_FAILED")
        ]
    elif scenario == "unauthorized_access":
        types = ["UNAUTHORIZED_REQUEST"] * rng.randint(2, 12)
    else:
        if scenario in {"normal_retry", "heldout_delayed_retry"}:
            types += [
                event
                for _ in range(1 + recipe % 2)
                for event in ("LOGIN_ATTEMPT", "LOGIN_FAILED")
            ]
        types += ["LOGIN_ATTEMPT", "LOGIN_SUCCESS"]
        if scenario == "invalid_sequence":
            types += ["RETURN", "VIEW_BALANCE", "TRANSFER_RECORDED"]
        elif scenario in {
            "normal_transfer",
            "transfer_burst",
            "heldout_paced_transfer",
        }:
            transfers = (
                1 + recipe % 3
                if scenario == "normal_transfer"
                else 15 + recipe
                if scenario == "transfer_burst"
                else 5 + recipe % 6
            )
            for _ in range(transfers):
                types += ["VIEW_BALANCE", "TRANSFER_REQUEST", "TRANSFER_RECORDED"]
        else:
            length = (
                25 + recipe
                if scenario == "normal_busy"
                else 50 + recipe * 2
                if scenario == "rapid_requests"
                else 2 + recipe % 9
            )
            types += [
                rng.choice(("VIEW_BALANCE", "VIEW_HISTORY")) for _ in range(length)
            ]
        types += ["LOGOUT"]
    gap = (
        (0.025, 0.15)
        if scenario == "failed_login_burst"
        else (0.3, 4.0)
        if scenario == "failed_login_paced"
        else (0.1, 4.5)
        if scenario == "heldout_jittered_login_failures"
        else (3.0, 9.0)
        if scenario == "heldout_delayed_retry"
        else (0.01, 0.08)
        if scenario == "rapid_requests"
        else (0.03, 0.3)
        if scenario == "transfer_burst"
        else (0.1, 1.0)
        if scenario == "unauthorized_access"
        else (0.4, 2.5)
        if scenario == "normal_busy"
        else (12.0, 80.0)
        if scenario == "heldout_slow_normal"
        else (1.0, 7.0)
        if scenario == "heldout_paced_transfer"
        else (1.0, 18.0)
    )
    timestamp, result = start, []
    for index, kind in enumerate(types):
        # Paired authentication/recording events happen in the same HTTP request.
        interval = rng.uniform(*gap)
        if kind in {"LOGIN_SUCCESS", "LOGIN_FAILED"}:
            # Server/database work happens between these events too. Apply the same
            # latency profiles to benign retries and attacks to avoid a timing shortcut.
            latency = (0.005, 0.05, 0.2, 0.8, 1.6, 2.5)[recipe % 6]
            interval = latency * rng.uniform(0.7, 1.3)
        elif kind == "TRANSFER_RECORDED":
            interval = rng.uniform(0.001, 0.012)
        if index:
            timestamp += interval * (0.8 + recipe / 50)
        result.append(ActivityEvent(kind, round(timestamp, 6), ENDPOINTS[kind]))
    return tuple(result)


def generate_sessions(count: int = 10000, seed: int = 42):
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("Session count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Seed must be an integer")
    rng = random.Random(seed)
    assignments = split_recipes(seed)
    names = list(SCENARIOS)
    weights = [SCENARIOS[name][1] for name in names]
    for index in range(count):
        scenario = rng.choices(names, weights=weights, k=1)[0]
        recipe = rng.randrange(RECIPE_COUNT)
        yield SyntheticSession(
            session_id=f"synthetic-{seed}-{index:06}",
            scenario=scenario,
            group_id=f"{scenario}:recipe-{recipe:02}",
            split=assignments[scenario, recipe],
            label=SCENARIOS[scenario][0],
            events=make_events(scenario, recipe, rng, 1735689600.0 + index * 900),
        )
