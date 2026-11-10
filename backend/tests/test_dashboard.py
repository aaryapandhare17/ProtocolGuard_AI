import json
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models.entities import SecurityEvent
from test_auth import app, signin
from test_blocking import admin_login, action


def test_overview_users_and_event_data_are_real_and_private(app):
    with TestClient(app) as bank, TestClient(app) as admin:
        signin(bank)
        raw_cookie = bank.cookies.get("pg_bank")
        bank.get("/api/bank/balance")
        assert admin.get("/api/admin/overview").status_code == 401
        admin_login(admin)
        overview = admin.get("/api/admin/overview").json()
        assert overview["total_users"] == 10 and overview["active_sessions"] == 1
        assert overview["events_analyzed"] == 3 and overview["blocked_accounts"] == 0
        assert sum(row["count"] for row in overview["threat_distribution"]) == 10
        assert len(overview["activity"]) == 24
        rows = admin.get("/api/admin/users?q=demo01").json()
        assert rows["total"] == 1 and rows["items"][0]["username"] == "demo01"
        assert admin.get("/api/admin/users?q=%25").json()["total"] == 0
        assert admin.get("/api/admin/users?limit=101").status_code == 422
        detail = admin.get("/api/admin/users/1").json()
        assert len(detail["events"]) == 3
        assert "password_hash" not in json.dumps(detail)
        assert raw_cookie not in json.dumps(detail)
        assert admin.get("/api/admin/users/999").status_code == 404
        events = admin.get("/api/admin/events?user_id=1&limit=2").json()
        assert len(events) == 2 and events[0]["event_type"] == "VIEW_BALANCE"
        assert events[0]["username"] == "demo01" and events[0]["fsm"]["valid"]
        admin_events = admin.get("/api/admin/events?q=LOGIN_SUCCESS").json()
        assert any(
            row["username"] == "admin" and row["account_type"] == "admin"
            for row in admin_events
        )
        before = admin.get(
            f"/api/admin/events?user_id=1&before_id={events[-1]['id']}"
        ).json()
        assert all(row["id"] < events[-1]["id"] for row in before)
        assert admin.get("/api/admin/events?q=DOES_NOT_EXIST").json() == []
        assert admin.get("/api/admin/events?limit=201").status_code == 422


def test_overview_reflects_blocks_alerts_and_decay(app):
    with TestClient(app) as admin:
        headers = admin_login(admin)
        action(admin, "/api/admin/users/1/block", headers)
        result = admin.get("/api/admin/overview").json()
        assert result["blocked_accounts"] == 1 and result["alerts_24h"] == 1
        assert result["recent_incidents"][0]["target"] == "demo01"
        assert result["recent_incidents"][0]["entity_type"] == "account"
        assert result["recent_incidents"][0]["resolved_at"] is None
        action(admin, "/api/admin/users/1/unblock", headers)
        assert admin.get("/api/admin/overview").json()["blocked_accounts"] == 0


def test_banking_users_cannot_read_dashboard_apis(app):
    with TestClient(app) as bank:
        signin(bank)
        for path in ("/overview", "/users", "/users/1", "/events"):
            assert bank.get("/api/admin" + path).status_code == 401


def test_opt_in_event_stream_and_reconnect_cursor(app):
    with TestClient(app) as bank, TestClient(app) as admin:
        signin(bank)
        admin_login(admin)
        with app.state.session_factory() as db:
            cursor = db.scalar(
                select(SecurityEvent.id).order_by(SecurityEvent.id.desc()).limit(1)
            )
        with admin.websocket_connect(f"/ws/admin/events?after_event_id={cursor}") as ws:
            assert ws.receive_json()["event_cursor"] == cursor
            bank.get("/api/bank/balance")
            message = ws.receive_json()
            assert message["type"] == "events"
            assert (
                len(message["events"]) == 1
                and message["events"][0]["event_type"] == "VIEW_BALANCE"
            )
            cursor = message["event_cursor"]
        with admin.websocket_connect(f"/ws/admin/events?after_event_id={cursor}") as ws:
            ws.receive_json()
            ws.send_text("ping")
            assert ws.receive_json()["type"] == "pong"
