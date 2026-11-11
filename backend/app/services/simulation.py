"""Fixed local scenarios execute real handlers in a disposable, isolated ASGI bank."""

import asyncio
import json
import random
import secrets
import time
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from sqlalchemy import select, update

from app.models.entities import (
    DetectionResult,
    IPRestriction,
    IPSecurityAlert,
    SecurityAlert,
    SecurityEvent,
    Session,
    User,
)
from app.security.credentials import hash_password
from app.services.admin_views import event_query, serialize_event

DEMO_ACCOUNTS = tuple(f"demo{index:02}" for index in range(1, 11))
SCENARIOS = {
    "normal": {
        "name": "Normal banking session",
        "description": "Sign in, browse, record one dummy transfer and log out.",
    },
    "failed_logins": {
        "name": "Repeated login failures",
        "description": "Bounded failed attempts, login throttling and a protected-access probe.",
    },
    "unauthorized": {
        "name": "Unauthorized balance access",
        "description": "Balance requests without a verified session; no account identity is invented.",
    },
    "rapid_requests": {
        "name": "Rapid request bursts",
        "description": "Authenticated browsing bursts with bounded concurrency.",
    },
    "transfer_burst": {
        "name": "Abnormal transfer requests",
        "description": "Repeated validated dummy transfer requests; no money moves.",
    },
    "mixed": {
        "name": "Mixed suspicious behavior",
        "description": "A revoked-session probe followed by renewed suspicious transfer activity.",
    },
}


async def execute_actor(
    sandbox, account, password, index, scenario, seed, shared_ip, limiter
):
    ip = "192.0.2.10" if shared_ip else f"192.0.2.{index + 10}"
    transport = httpx.ASGITransport(app=sandbox, client=(ip, 5000 + index))
    rng = random.Random(f"{seed}:{account}")
    requests = []
    async with httpx.AsyncClient(
        transport=transport, base_url="http://simulation.local"
    ) as client:

        async def call(method, path, body=None, csrf=None):
            async with limiter:
                response = await client.request(
                    method,
                    path,
                    json=body,
                    headers={"X-CSRF-Token": csrf} if csrf else {},
                )
                requests.append(
                    {
                        "step": len(requests) + 1,
                        "method": method,
                        "path": path,
                        "status": response.status_code,
                    }
                )
                return response

        async def login():
            response = await call(
                "POST", "/api/auth/login", {"username": account, "password": password}
            )
            return (
                response.json().get("csrf_token")
                if response.status_code == 200
                else None
            )

        try:
            if scenario == "failed_logins":
                for _ in range(32):
                    response = await call(
                        "POST",
                        "/api/auth/login",
                        {
                            "username": account,
                            "password": "invalid-simulation-password",
                        },
                    )
                    if response.status_code == 403:
                        break
                await call("GET", "/api/bank/balance")
            elif scenario == "unauthorized":
                for _ in range(8):
                    await call("GET", "/api/bank/balance")
            else:
                csrf = await login()
                if csrf:
                    if scenario == "normal":
                        await call("GET", "/api/bank/balance")
                        await call("GET", "/api/bank/history")
                        await call(
                            "POST",
                            "/api/bank/transfer-request",
                            {
                                "recipient": "Demo recipient",
                                "amount_cents": rng.randint(1, 100) * 100,
                            },
                            csrf,
                        )
                        await call("POST", "/api/auth/logout", csrf=csrf)
                    elif scenario == "rapid_requests":
                        for _ in range(12):
                            responses = await asyncio.gather(
                                *(
                                    call(
                                        "GET",
                                        rng.choice(
                                            ("/api/bank/balance", "/api/bank/history")
                                        ),
                                    )
                                    for _ in range(4)
                                )
                            )
                            if any(
                                response.status_code == 403 for response in responses
                            ):
                                break
                        await call("GET", "/api/bank/balance")
                    elif scenario == "transfer_burst":
                        for _ in range(18):
                            response = await call(
                                "POST",
                                "/api/bank/transfer-request",
                                {"recipient": "Demo recipient", "amount_cents": 100},
                                csrf,
                            )
                            if response.status_code == 403:
                                break
                        await call("GET", "/api/bank/balance")
                    elif scenario == "mixed":
                        token = client.cookies.get("pg_bank")
                        await call("POST", "/api/auth/logout", csrf=csrf)
                        client.cookies.set(
                            "pg_bank", token, domain="simulation.local", path="/"
                        )
                        for _ in range(3):
                            await call("GET", "/api/bank/balance")
                        client.cookies.clear()
                        csrf = await login()
                        if csrf:
                            for _ in range(18):
                                response = await call(
                                    "POST",
                                    "/api/bank/transfer-request",
                                    {
                                        "recipient": "Demo recipient",
                                        "amount_cents": 100,
                                    },
                                    csrf,
                                )
                                if response.status_code == 403:
                                    break
                            await call("GET", "/api/bank/balance")
            return {
                "account": account,
                "simulated_ip": ip,
                "status": "completed",
                "requests": requests,
            }
        except Exception as error:
            return {
                "account": account,
                "simulated_ip": ip,
                "status": "failed",
                "error": type(error).__name__,
                "requests": requests,
            }


async def run_sandbox(source, accounts, scenario, seed, shared_ip, enforcement):
    from app.main import create_app

    started = time.perf_counter()
    with TemporaryDirectory(prefix="protocolguard-simulation-") as temporary:
        config = source.state.settings.model_copy(
            update={
                "database_url": f"sqlite:///{Path(temporary) / 'sandbox.db'}",
                "ml_enabled": False,
                "simulation_enabled": False,
                "block_threshold": enforcement["threshold"],
                "auto_block_enabled": enforcement["automatic_blocking"],
            }
        )
        sandbox = create_app(config)
        async with sandbox.router.lifespan_context(sandbox):
            sandbox.state.detector, sandbox.state.ml_status = (
                source.state.detector,
                source.state.ml_status,
            )
            password = secrets.token_urlsafe(32)
            with sandbox.state.session_factory.begin() as db:
                for account in accounts:
                    db.add(
                        User(
                            username=account,
                            password_hash=hash_password(password),
                            balance_cents=125000,
                        )
                    )
            limiter = asyncio.Semaphore(4)
            actors = await asyncio.gather(
                *(
                    execute_actor(
                        sandbox,
                        account,
                        password,
                        index,
                        scenario,
                        seed,
                        shared_ip,
                        limiter,
                    )
                    for index, account in enumerate(accounts)
                )
            )
            with sandbox.state.session_factory.begin() as db:
                # Label before exporting the isolated snapshot; no rows enter the live event table.
                db.execute(update(SecurityEvent).values(simulated=True))
                users = {user.username: user for user in db.scalars(select(User))}
                event_rows = db.execute(event_query().order_by(SecurityEvent.id)).all()
                events = [serialize_event(*row) for row in event_rows]
                risk_by_user = {}
                for detection in db.scalars(select(DetectionResult)):
                    payload = json.loads(detection.evidence)
                    if detection.user_id:
                        risk_by_user[detection.user_id] = max(
                            risk_by_user.get(detection.user_id, 0), payload["score"]
                        )
                restrictions = db.scalars(
                    select(IPRestriction).where(IPRestriction.active.is_(True))
                ).all()
                from app.models.entities import SuspiciousIP

                restricted = {
                    db.get(SuspiciousIP, row.ip_id).address for row in restrictions
                }
                for actor in actors:
                    user = users[actor["account"]]
                    actor.update(
                        {
                            "account_risk": user.risk_score,
                            "peak_risk": risk_by_user.get(user.id, 0),
                            "account_blocked": user.blocked,
                            "ip_restricted": actor["simulated_ip"] in restricted,
                            "outcomes": dict(
                                Counter(str(row["status"]) for row in actor["requests"])
                            ),
                            "final_states": [
                                session.state
                                for session in db.scalars(
                                    select(Session).where(Session.user_id == user.id)
                                )
                            ],
                        }
                    )
                alerts = [
                    {
                        "entity": "account",
                        "account": next(
                            name
                            for name, user in users.items()
                            if user.id == row.user_id
                        ),
                        "reason": row.reason,
                        "evidence": json.loads(row.evidence),
                    }
                    for row in db.scalars(select(SecurityAlert))
                ]
                alerts += [
                    {
                        "entity": "ip",
                        "ip_address": db.get(SuspiciousIP, row.ip_id).address,
                        "reason": row.reason,
                        "evidence": json.loads(row.evidence),
                    }
                    for row in db.scalars(select(IPSecurityAlert))
                ]
                return {
                    "simulated": True,
                    "scope": "isolated_demo_clones",
                    "actors": actors,
                    "events": events,
                    "alerts": alerts,
                    "summary": {
                        "actors": len(actors),
                        "requests": sum(len(actor["requests"]) for actor in actors),
                        "events": len(events),
                        "blocked_accounts": sum(
                            actor["account_blocked"] for actor in actors
                        ),
                        "restricted_ips": len(restricted),
                        "alerts": len(alerts),
                        "duration_ms": (time.perf_counter() - started) * 1000,
                        "model_status": source.state.ml_status,
                    },
                    "limitations": [
                        "Runs use actual handler execution times; a fixed seed reproduces the plan, not exact timing or risk scores.",
                        "Accounts, session identifiers, addresses and events belong to this sandbox only; they are not live record links.",
                    ],
                }
