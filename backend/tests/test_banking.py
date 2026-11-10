from sqlalchemy import select
from fastapi.testclient import TestClient
from app.models.entities import SecurityEvent
from test_auth import app, signin


def test_actions_and_independent_history(app):
    with TestClient(app) as first, TestClient(app) as second:
        csrf = signin(first).json()["csrf_token"]
        signin(second, "demo02")
        assert first.get("/api/bank/balance").json()["balance_cents"] == 142500
        response = first.post("/api/bank/transfer-request", json={"amount_cents": 10000, "recipient": "Demo recipient"}, headers={"X-CSRF-Token": csrf})
        assert response.json()["status"] == "simulation_only"
        assert first.get("/api/bank/balance").json()["balance_cents"] == 142500
        actions = first.get("/api/bank/history").json()
        assert any(e["action"] == "TRANSFER_REQUEST" for e in actions)
        assert not any(e["action"] == "TRANSFER_REQUEST" for e in second.get("/api/bank/history").json())
        assert first.post("/api/bank/transfer-request", json={"amount_cents": -1, "recipient": "abc"}, headers={"X-CSRF-Token": csrf}).status_code == 422
    with app.state.session_factory() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.event_type == "TRANSFER_REQUEST")).user_id == 1


def test_actions_require_auth(app):
    with TestClient(app) as client:
        assert client.get("/api/bank/balance").status_code == 401
        assert client.get("/api/bank/history").status_code == 401
        assert client.post("/api/bank/transfer-request", json={"amount_cents":100,"recipient":"abc"}).status_code == 401
