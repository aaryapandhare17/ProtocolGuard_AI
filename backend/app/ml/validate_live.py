"""Build-time acceptance checks using real handlers/models and controlled UTC time.

All HTTP traffic stays in a disposable local ASGI app. No live account is accessed.
"""

import argparse
from contextlib import contextmanager
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


@contextmanager
def controlled_clock():
    clock = {"seconds": -10.0, "request_start": -10.0}
    epoch = datetime(2030, 1, 1, tzinfo=timezone.utc)

    class ReplayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = epoch + timedelta(seconds=clock["seconds"])
            return value.replace(tzinfo=None) if tz is None else value.astimezone(tz)

    with patch("app.database.store.datetime", ReplayDateTime):
        yield clock


def acceptance_app(artifacts, temporary):
    from app.main import create_app

    return create_app(Settings(
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
    ))


def seed_acceptance_bank(app):
    if app.state.ml_status != "ready":
        raise ValueError("Acceptance checks require ready saved models")
    seed(app.state.session_factory, "acceptance-bank-password", "acceptance-admin-password")


def replay(artifacts, latency, gap, *, failed_logins=15, normal_retry=False):
    from app.api import routes

    original_record = routes.record

    def timed_record(db, request, kind, *args, **kwargs):
        if kind in {"LOGIN_FAILED", "LOGIN_SUCCESS"}:
            clock["seconds"] = clock["request_start"] + latency
        return original_record(db, request, kind, *args, **kwargs)

    with TemporaryDirectory(prefix="protocolguard-ml-acceptance-") as temporary:
        app = acceptance_app(artifacts, temporary)
        with controlled_clock() as clock, patch.object(routes, "record", timed_record):
            with TestClient(app, client=("192.0.2.60", 5000)) as bank:
                seed_acceptance_bank(app)
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


TRANSFER_TIMING_CASES = (
    ((7, 7, 7, 7, 7, 7), False),
    ((3, 8, 5, 11, 4, 9), True),
    ((10, 10, 10, 10, 10, 10), False),
)


def replay_transfers(artifacts, gaps, *, view_balance):
    with TemporaryDirectory(prefix="protocolguard-ml-transfers-") as temporary:
        app = acceptance_app(artifacts, temporary)
        with controlled_clock() as clock, TestClient(app) as bank:
            seed_acceptance_bank(app)
            login = bank.post(
                "/api/auth/login",
                json={"username": "demo02", "password": "acceptance-bank-password"},
            )
            login.raise_for_status()
            headers = {"X-CSRF-Token": login.json()["csrf_token"]}
            clock["seconds"] = 0.0
            statuses = []
            for gap in gaps:
                clock["seconds"] += gap
                if view_balance:
                    bank.get("/api/bank/balance").raise_for_status()
                    clock["seconds"] += 0.01
                status = bank.post(
                    "/api/bank/transfer-request",
                    headers=headers,
                    json={"recipient": "Demo recipient", "amount_cents": 100},
                ).status_code
                statuses.append(status)
                if status == 403:
                    break
                if status != 200:
                    raise ValueError(f"Unexpected transfer response: {status}")
            protected_status = bank.get("/api/bank/balance").status_code
            with app.state.session_factory() as db:
                user = db.scalar(select(User).where(User.username == "demo02"))
                block = db.scalar(select(BlockedEntity).where(BlockedEntity.user_id == user.id))
                alert = db.scalar(select(SecurityAlert).where(SecurityAlert.user_id == user.id))
                return {
                    "gaps_seconds": gaps,
                    "view_balance_between_transfers": view_balance,
                    "transfer_statuses": statuses,
                    "elapsed_seconds": clock["seconds"],
                    "blocked": user.blocked,
                    "block_source": block.source if block else None,
                    "alert_recorded": alert is not None,
                    "protected_status": protected_status,
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
    transfers = [
        replay_transfers(artifacts, gaps, view_balance=view_balance)
        for gaps, view_balance in TRANSFER_TIMING_CASES
    ]
    normal_transfers = [
        replay_transfers(artifacts, gaps[:3], view_balance=view_balance)
        for gaps, view_balance in TRANSFER_TIMING_CASES
    ]
    passed = passed and not paced["blocked"] and all(
        row["blocked"]
        and row["block_source"] == "automatic"
        and row["alert_recorded"]
        and row["transfer_statuses"][-1] == 403
        and row["protected_status"] == 403
        for row in transfers
    ) and all(
        not row["blocked"]
        and row["transfer_statuses"] == [200, 200, 200]
        and row["protected_status"] == 200
        for row in normal_transfers
    )
    return {
        "passed": passed,
        "threshold": 60,
        "paced_transfer_cases": transfers,
        "normal_transfer_controls": normal_transfers,
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
                "paced_transfer_cases": len(report["paced_transfer_cases"]),
                "normal_transfer_controls": len(report["normal_transfer_controls"]),
                "threshold": 60,
            }
        )
    )
    if not report["passed"]:
        raise SystemExit("Model acceptance gate failed; do not deploy these artifacts")


if __name__ == "__main__":
    main()
