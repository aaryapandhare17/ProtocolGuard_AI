from fastapi.testclient import TestClient
from app.main import create_app


def test_health():
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "protocolguard-api"}


def test_cors_rejects_unknown_origin():
    with TestClient(create_app()) as client:
        response = client.options("/api/health", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"
        })
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
