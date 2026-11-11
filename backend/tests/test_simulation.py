import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from app.models.entities import (
    AdminAuditLog,
    BlockedEntity,
    IPRestriction,
    SecurityAlert,
    SecurityEvent,
    User,
)
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_auth import app, signin
from test_blocking import admin_login


def payload(scenario="normal", accounts=None, **extra):
    return {
        "scenario": scenario,
        "accounts": accounts or ["demo01", "demo02"],
        "seed": 42,
        "shared_ip": False,
        "confirmed": True,
        "note": "Controlled lab verification",
        **extra,
    }


def source_snapshot(app):
    with app.state.session_factory() as db:
        return {
            "users": [
                (u.id, u.risk_score, u.blocked, u.balance_cents)
                for u in db.scalars(select(User).order_by(User.id))
            ],
            "events": db.scalar(select(func.count()).select_from(SecurityEvent)),
            "blocks": db.scalar(select(func.count()).select_from(BlockedEntity)),
            "ips": db.scalar(select(func.count()).select_from(IPRestriction)),
            "alerts": db.scalar(select(func.count()).select_from(SecurityAlert)),
        }


def test_normal_multiuser_run_persists_without_live_side_effects(app):
    with TestClient(app) as admin:
        headers = admin_login(admin)
        before = source_snapshot(app)
        response = admin.post("/api/simulation/run", headers=headers, json=payload())
        assert response.status_code == 200, response.text
        run = response.json()
        assert run["status"] == "completed"
        result = run["result"]
        assert result["simulated"] and len(result["actors"]) == 2
        assert all(
            actor["outcomes"] == {"200": 5} and not actor["account_blocked"]
            for actor in result["actors"]
        )
        assert all(event["simulated"] for event in result["events"])
        assert {actor["simulated_ip"] for actor in result["actors"]} == {
            "192.0.2.10",
            "192.0.2.11",
        }
        assert source_snapshot(app) == before
        assert admin.get("/api/simulation/runs").json()[0]["id"] == run["id"]
        assert admin.get("/api/simulation/runs/" + run["id"]).json()["result"] == result
        text = json.dumps(result)
        assert "csrf_token" not in text and "password_hash" not in text
        assert admin.get("/api/simulation/runs/missing").status_code == 404
        with app.state.session_factory() as db:
            assert {row.action for row in db.scalars(select(AdminAuditLog))} >= {
                "SIMULATION_START",
                "SIMULATION_COMPLETE",
            }


def test_all_abuse_scenarios_use_real_handlers_and_isolated_enforcement(app):
    class HighEvidence:
        def predict(self, *args, **kwargs):
            return {
                "random_forest": {"score": 1},
                "isolation_forest": {"anomaly_evidence": 1},
            }

    with TestClient(app) as admin:
        headers = admin_login(admin)
        before = source_snapshot(app)
        app.state.detector, app.state.ml_status = HighEvidence(), "ready"
        for scenario in (
            "unauthorized",
            "rapid_requests",
            "transfer_burst",
            "mixed",
            "failed_logins",
        ):
            response = admin.post(
                "/api/simulation/run",
                headers=headers,
                json=payload(scenario, ["demo03"]),
            )
            assert response.status_code == 200, response.text
            run = response.json()
            assert run["status"] == "completed", run
            actor = run["result"]["actors"][0]
            assert all(row["path"].startswith("/api/") for row in actor["requests"])
            if scenario == "unauthorized":
                assert actor["outcomes"] == {"401": 8} and actor["account_risk"] == 0
                assert any(
                    event["fsm"] and not event["fsm"]["valid"]
                    for event in run["result"]["events"]
                )
            elif scenario == "failed_logins":
                assert actor["account_blocked"] and actor["ip_restricted"]
                assert "403" in actor["outcomes"]
            else:
                assert actor["account_blocked"] and "403" in actor["outcomes"]
            if scenario == "mixed":
                assert any(
                    event["event_type"] == "UNAUTHORIZED_REQUEST"
                    for event in run["result"]["events"]
                )
        assert source_snapshot(app) == before


def test_simulator_requires_admin_csrf_confirmation_and_fixed_inputs(app):
    with TestClient(app) as client:
        assert client.post("/api/simulation/run", json=payload()).status_code == 401
        signin(client)
        assert client.get("/api/simulation/scenarios").status_code == 401
        headers = admin_login(client)
        assert client.post("/api/simulation/run", json=payload()).status_code == 403
        for body in (
            payload(accounts=["not-a-demo"]),
            payload(accounts=["demo01", "demo01"]),
            payload(scenario="external_attack"),
            payload(target_url="https://external.example"),
            payload(confirmed=False),
            payload(accounts=["demo01"] * 11),
        ):
            assert (
                client.post(
                    "/api/simulation/run", headers=headers, json=body
                ).status_code
                == 422
            )
        app.state.settings = app.state.settings.model_copy(
            update={"protocolguard_env": "production"}
        )
        assert not client.get("/api/simulation/scenarios").json()["enabled"]
        assert (
            client.post(
                "/api/simulation/run", headers=headers, json=payload()
            ).status_code
            == 403
        )


def test_run_limit_and_live_database_remains_available(app, monkeypatch):
    import app.api.simulation as simulation

    started, release = Event(), Event()

    async def isolated_wait(*args, **kwargs):
        started.set()
        await asyncio.to_thread(release.wait, 10)
        return {"actors": [], "summary": {"actors": 0}}

    monkeypatch.setattr(simulation, "run_sandbox", isolated_wait)
    with TestClient(app) as admin:
        headers = admin_login(admin)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                lambda: admin.post(
                    "/api/simulation/run", headers=headers, json=payload()
                )
            )
            assert started.wait(3)
            try:
                assert admin.get("/api/admin/overview").status_code == 200
                assert (
                    admin.get("/api/simulation/runs").json()[0]["status"] == "running"
                )
            finally:
                release.set()
            assert pending.result(timeout=5).status_code == 200
        assert app.state.simulation_slots.acquire(
            False
        ) and app.state.simulation_slots.acquire(False)
        try:
            assert (
                admin.post(
                    "/api/simulation/run", headers=headers, json=payload()
                ).status_code
                == 409
            )
        finally:
            app.state.simulation_slots.release()
            app.state.simulation_slots.release()


def test_shared_virtual_ip_is_explicit_and_model_failure_is_not_fabricated(app):
    with TestClient(app) as admin:
        headers = admin_login(admin)
        response = admin.post(
            "/api/simulation/run", headers=headers, json=payload(shared_ip=True)
        )
        result = response.json()["result"]
        assert result["summary"]["model_status"] == "disabled"
        assert {actor["simulated_ip"] for actor in result["actors"]} == {"192.0.2.10"}
        assert not any(actor["account_blocked"] for actor in result["actors"])


def test_revoked_admin_cannot_receive_completed_result(app, monkeypatch):
    import app.api.simulation as simulation

    started, release = Event(), Event()

    async def waiting(*args, **kwargs):
        started.set()
        await asyncio.to_thread(release.wait, 10)
        return {"actors": [], "summary": {"actors": 0}}

    monkeypatch.setattr(simulation, "run_sandbox", waiting)
    with TestClient(app) as admin:
        headers = admin_login(admin)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                lambda: admin.post(
                    "/api/simulation/run", headers=headers, json=payload()
                )
            )
            assert started.wait(3)
            try:
                assert (
                    admin.post("/api/admin/auth/logout", headers=headers).status_code
                    == 200
                )
            finally:
                release.set()
            assert pending.result(timeout=5).status_code == 401
        admin_login(admin)
        assert admin.get("/api/simulation/runs").json()[0]["status"] == "completed"


def test_ten_demo_actors_and_saved_results_survive_restart(app):
    from app.main import create_app

    with TestClient(app) as admin:
        headers = admin_login(admin)
        run = admin.post(
            "/api/simulation/run",
            headers=headers,
            json=payload(accounts=[f"demo{i:02}" for i in range(1, 11)]),
        ).json()
        assert run["status"] == "completed" and len(run["result"]["actors"]) == 10
        assert all(len(actor["requests"]) <= 50 for actor in run["result"]["actors"])
    reopened = create_app(app.state.settings)
    with TestClient(reopened) as admin:
        admin_login(admin)
        assert (
            admin.get("/api/simulation/runs/" + run["id"]).json()["result"]
            == run["result"]
        )
