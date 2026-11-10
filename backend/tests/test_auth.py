from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import Settings
from app.main import create_app
from app.seed import seed
from app.models.entities import SecurityEvent, Session, User
from app.database.store import now


@pytest.fixture
def app(tmp_path):
    instance = create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db", ml_enabled=False))
    with TestClient(instance):
        seed(instance.state.session_factory, "bank-test-password", "admin-test-password")
        yield instance


def signin(client, username="demo01", password="bank-test-password", admin=False):
    return client.post("/api/admin/auth/login" if admin else "/api/auth/login", json={"username": username, "password": password})


def test_login_logout_csrf_and_revocation(app):
    with TestClient(app) as client:
        response = signin(client)
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/api/auth/me").json()["username"] == "demo01"
        assert client.post("/api/auth/logout").status_code == 403
        token = client.cookies.get("pg_bank")
        assert client.post("/api/auth/logout", headers={"X-CSRF-Token": response.json()["csrf_token"]}).status_code == 200
        client.cookies.set("pg_bank", token)
        assert client.get("/api/auth/me").status_code == 401


def test_failure_evidence_and_rate_limit(app):
    with TestClient(app) as client:
        for _ in range(20):
            assert signin(client, password="wrong").status_code == 401
        assert signin(client).status_code == 429
    with app.state.session_factory() as db:
        events = db.scalars(select(SecurityEvent)).all()
        assert sum(e.event_type == "LOGIN_FAILED" for e in events) == 20
        assert "wrong" not in str([e.evidence for e in events])


def test_role_isolation_and_expiry(app):
    with TestClient(app) as client:
        assert signin(client).status_code == 200
        assert client.get("/api/admin/auth/me").status_code == 401
        assert signin(client, "admin", "admin-test-password", True).status_code == 200
        assert client.get("/api/admin/auth/me").status_code == 200
        with app.state.session_factory.begin() as db:
            for session in db.scalars(select(Session)):
                session.expires_at = now() - timedelta(seconds=1)
        assert client.get("/api/auth/me").status_code == 401


def test_parallel_users_and_password_storage(app):
    def run(index):
        with TestClient(app) as client:
            assert signin(client, f"demo{index:02}").status_code == 200
            return client.get("/api/auth/me").json()["username"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(pool.map(run, [1, 2, 3])) == ["demo01", "demo02", "demo03"]
    with app.state.session_factory() as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 10
        assert all(u.password_hash.startswith("scrypt$") for u in users)
        assert len({u.password_hash for u in users}) == 10


def test_block_and_untrusted_origin(app):
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username":"demo01", "password":"bank-test-password"}, headers={"Origin":"https://evil.example"}).status_code == 403
        with app.state.session_factory.begin() as db:
            db.get(User, 1).blocked = True
        assert signin(client).status_code == 403
