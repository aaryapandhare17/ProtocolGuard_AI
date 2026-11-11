from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.database.store import configure
from app.deploy import provision, validate_hosting
from app.main import create_app
from app.models.entities import Admin, User
from app.security.credentials import verify_password


@pytest.fixture
def hosted(tmp_path):
    for name in ("bank", "admin"):
        root = tmp_path / "web" / name
        (root / "assets").mkdir(parents=True)
        (root / "index.html").write_text(f"<html>{name}</html>")
        (root / "assets" / "app-hash.js").write_text(f'console.log("{name}")')
    return Settings(
        protocolguard_env="production",
        database_url=f"sqlite:///{tmp_path}/hosted.db",
        cors_origins="https://bank.example",
        static_directory=str(tmp_path / "web"),
        ml_enabled=False,
    )


def test_compiled_apps_deep_links_and_reserved_api_routes(hosted):
    with TestClient(create_app(hosted), base_url="https://bank.example") as client:
        for path in ("/", "/login", "/dashboard"):
            response = client.get(path)
            assert response.status_code == 200 and response.text == "<html>bank</html>"
            assert response.headers["cache-control"] == "no-cache"
        for path in ("/admin/", "/admin/users/7", "/admin/simulation"):
            assert client.get(path).text == "<html>admin</html>"
        assert (
            client.get("/admin", follow_redirects=False).headers["location"]
            == "/admin/"
        )
        for path in ("/assets/app-hash.js", "/admin/assets/app-hash.js"):
            response = client.get(path)
            assert response.status_code == 200
            assert "immutable" in response.headers["cache-control"]
        for path in (
            "/assets/missing.js",
            "/admin/assets/missing.js",
            "/.env",
            "/api/not-a-route",
            "/ws/not-a-route",
            "/admin/api/not-a-route",
        ):
            response = client.get(path)
            assert response.status_code == 404 and "<html>" not in response.text, path
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/admin/auth/me").status_code == 401
        assert client.post("/not-a-route").status_code == 405


def test_hosting_provisioning_is_explicit_and_retains_passwords(hosted, monkeypatch):
    monkeypatch.delenv("PROVISION_DEMO_ACCOUNTS", raising=False)
    provision(hosted)
    database_path = Path(hosted.database_url.removeprefix("sqlite:///"))
    assert not database_path.exists()
    monkeypatch.setenv("PROVISION_DEMO_ACCOUNTS", "true")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "hosted-bank-password")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "hosted-admin-password")
    provision(hosted)
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-new-ignored-password")
    provision(hosted)
    engine, factory = configure(hosted.database_url)
    try:
        with factory() as db:
            assert len(list(db.scalars(select(User)))) == 10
            admin = db.scalar(select(Admin))
            assert verify_password("hosted-admin-password", admin.password_hash)
    finally:
        engine.dispose()
    with TestClient(create_app(hosted), base_url="https://bank.example") as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "hosted-admin-password"},
        )
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]
        assert client.get("/api/admin/auth/me").status_code == 200
        assert not client.get("/api/simulation/scenarios").json()["enabled"]
        assert (
            client.post(
                "/api/simulation/run",
                headers={"X-CSRF-Token": response.json()["csrf_token"]},
                json={
                    "scenario": "normal",
                    "accounts": ["demo01"],
                    "confirmed": True,
                    "note": "Hosted guard verification",
                },
            ).status_code
            == 403
        )


def test_hosting_rejects_unsafe_origins_and_proxy_trust(hosted):
    validate_hosting(hosted, "")
    validate_hosting(hosted, "127.0.0.1,10.1.0.0/16,::1")
    for proxies in ("*", "localhost", "invalid"):
        with pytest.raises(ValueError):
            validate_hosting(hosted, proxies)
    for origin in (
        "http://bank.example",
        "https://bank.example/",
        "*",
        "https://bank.example/path",
        "https://user:pass@bank.example",
    ):
        with pytest.raises(ValueError):
            validate_hosting(hosted.model_copy(update={"cors_origins": origin}), "")
    with pytest.raises(ValueError):
        validate_hosting(
            hosted.model_copy(update={"protocolguard_env": "development"}), ""
        )
    with pytest.raises(ValueError):
        validate_hosting(hosted.model_copy(update={"static_directory": None}), "")
    with pytest.raises(RuntimeError, match="frontend is missing"):
        create_app(hosted.model_copy(update={"static_directory": "/missing/build"}))


def test_render_origin_is_configured_before_server_starts(hosted, monkeypatch):
    from app import deploy

    monkeypatch.setattr(deploy, "settings", hosted)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://assigned-service.onrender.com/")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("PROVISION_DEMO_ACCOUNTS", raising=False)
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    captured = {}
    monkeypatch.setattr(
        deploy.uvicorn, "run", lambda app, **options: captured.update(options)
    )
    deploy.main()
    assert hosted.cors_origins == "https://assigned-service.onrender.com"
    assert captured["workers"] == 1 and not captured["proxy_headers"]
    monkeypatch.setenv("CORS_ORIGINS", "https://bank.example")
    hosted.cors_origins = "https://bank.example"
    deploy.main()
    assert hosted.cors_origins == "https://bank.example"
