"""Build-time acceptance checks using real handlers/models and controlled UTC time.

All HTTP traffic stays in a disposable local ASGI app. No live account is accessed.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.models.entities import BlockedEntity, SecurityAlert, User
from app.seed import seed

TIMING_CASES = (
    (0.005, 0.05),
    (0.5, 2.0),
    (1.0, 3.0),
    (1.5, 2.5),
    (2.0, 2.0),
    (3.0, 0.5),
)


def replay(artifacts, latency, gap, *, failed_logins=15, normal_retry=False):
    from app.main import create_app
    from app.api import routes

    clock = {"seconds": -10.0, "request_start": -10.0}
    epoch = datetime(2030, 1, 1, tzinfo=timezone.utc)

    class ReplayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = epoch + timedelta(seconds=clock["seconds"])
            return value.replace(tzinfo=None) if tz is None else value.astimezone(tz)

    original_record = routes.record

    def timed_record(db, request, kind, *args, **kwargs):
        if kind in {"LOGIN_FAILED", "LOGIN_SUCCESS"}:
            clock["seconds"] = clock["request_start"] + latency
        return original_record(db, request, kind, *args, **kwargs)

    with TemporaryDirectory(prefix="protocolguard-ml-acceptance-") as temporary:
        config = Settings(
            database_url=f"sqlite:///{temporary}/bank.db",
            ml_model_directory=str(Path(artifacts).resolve()),
            protocolguard_env="development",
            require_postgres=False,
            require_signed_client_ip=False,
            serve_frontends=False,
            block_threshold=60,
            auto_block_enabled=True,
            ip_auto_restrict_enabled=False,
            ml_enabled=True,
            risk_fsm_weight=0.30,
            risk_rf_weight=0.35,
            risk_if_weight=0.10,
            risk_behavior_weight=0.25,
            risk_window_seconds=60,
            risk_half_life_seconds=600,
        )
        app = create_app(config)
        with (
            patch("app.database.store.datetime", ReplayDateTime),
            patch.object(routes, "record", timed_record),
        ):
            with TestClient(app, client=("192.0.2.60", 5000)) as bank:
                seed(
                    app.state.session_factory,
                    "acceptance-bank-password",
                    "acceptance-admin-password",
                )
                if app.state.ml_status != "ready":
                    raise ValueError("Acceptance checks require ready saved models")
                # Preserve a verified session to prove backend denial after enforcement.
                bank.post(
                    "/api/auth/login",
                    json={"username": "demo02", "password": "acceptance-bank-password"},
                )
                rows = []
                with TestClient(app, client=("192.0.2.61", 5001)) as attempts:
                    for number in range(1, failed_logins + 1):
                        clock["request_start"] = (number - 1) * (latency + gap)
                        clock["seconds"] = clock["request_start"]
                        response = attempts.post(
                            "/api/auth/login",
                            json={
                                "username": "demo02",
                                "password": "deliberately-invalid-acceptance-password",
                            },
                        )
                        with app.state.session_factory() as db:
                            user = db.scalar(
                                select(User).where(User.username == "demo02")
                            )
                            rows.append(
                                {
                                    "attempt": number,
                                    "seconds": clock["seconds"],
                                    "response_status": response.status_code,
                                    "score": user.risk_score,
                                    "blocked": user.blocked,
                                }
                            )
                            if user.blocked:
                                break
                    if normal_retry:
                        clock["request_start"] = clock["seconds"] + gap
                        clock["seconds"] = clock["request_start"]
                        response = attempts.post(
                            "/api/auth/login",
                            json={
                                "username": "demo02",
                                "password": "acceptance-bank-password",
                            },
                        )
                        if response.status_code != 200:
                            raise ValueError("Normal retry prevented a valid login")
                clock["seconds"] += 0.1
                protected = bank.get("/api/bank/balance")
                with app.state.session_factory() as db:
                    user = db.scalar(select(User).where(User.username == "demo02"))
                    block = db.scalar(
                        select(BlockedEntity).where(BlockedEntity.user_id == user.id)
                    )
                    alert = db.scalar(
                        select(SecurityAlert).where(SecurityAlert.user_id == user.id)
                    )
                    other = db.scalar(select(User).where(User.username == "demo03"))
                    return {
                        "latency_seconds": latency,
                        "gap_seconds": gap,
                        "requested_failures": failed_logins,
                        "attempts": rows,
                        "blocked": user.blocked,
                        "block_source": block.source if block else None,
                        "alert_reason": alert.reason if alert else None,
                        "protected_status": protected.status_code,
                        "unrelated_account_unchanged": not other.blocked
                        and other.risk_score == 0,
                    }


def validate(artifacts):
    attacks = [replay(artifacts, latency, gap) for latency, gap in TIMING_CASES]
    controls = [
        replay(artifacts, latency, gap, failed_logins=count, normal_retry=True)
        for latency, gap in ((0.005, 0.05), (0.5, 2), (2, 4))
        for count in (0, 1, 2, 3)
    ]
    paced = replay(artifacts, 1, 25)
    passed = all(
        row["blocked"]
        and row["block_source"] == "automatic"
        and row["protected_status"] == 403
        and len(row["attempts"]) <= 15
        and row["attempts"][-1]["seconds"] <= 60
        and row["unrelated_account_unchanged"]
        for row in attacks
    )
    passed = passed and all(
        not row["blocked"]
        and row["protected_status"] == 200
        and row["unrelated_account_unchanged"]
        for row in controls
    )
    passed = passed and not paced["blocked"]
    return {
        "passed": passed,
        "threshold": 60,
        "risk_policy_unchanged": True,
        "scope": "isolated ASGI replay with controlled timestamps; not a live-network timing guarantee",
        "attack_cases": attacks,
        "normal_retry_controls": controls,
        "outside_window_control": paced,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "attack_cases": len(report["attack_cases"]),
                "normal_retry_controls": len(report["normal_retry_controls"]),
                "threshold": 60,
            }
        )
    )
    if not report["passed"]:
        raise SystemExit("Model acceptance gate failed; do not deploy these artifacts")


if __name__ == "__main__":
    main()
