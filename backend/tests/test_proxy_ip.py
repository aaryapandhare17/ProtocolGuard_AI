import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models.entities import SecurityEvent, SuspiciousIP
from app.security.proxy_ip import verified_client_ip
from app.seed import seed

KEY = "public-test-key-only-not-for-production-12345"


def signed(address, method="GET", path="/api/bank/balance", timestamp=None):
    sent = str(int(time.time()) if timestamp is None else timestamp)
    message = "\n".join(("pg-ip-v1", sent, method, path, address))
    return {
        "x-protocolguard-client-ip": address,
        "x-protocolguard-client-time": sent,
        "x-protocolguard-client-signature": hmac.new(
            KEY.encode(), message.encode(), hashlib.sha256
        ).hexdigest(),
    }


def scope(headers, method="GET", path="/api/bank/balance"):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "headers": [(name.encode(), value.encode()) for name, value in headers.items()],
    }


def test_signature_binds_address_path_method_and_time():
    headers = signed("203.0.113.15", timestamp=1700000000)
    assert (
        verified_client_ip(scope(headers), KEY, timestamp=1700000010) == "203.0.113.15"
    )
    for changed in (
        {**headers, "x-protocolguard-client-ip": "198.51.100.6"},
        {**headers, "x-protocolguard-client-signature": "0" * 64},
    ):
        with pytest.raises(ValueError):
            verified_client_ip(scope(changed), KEY, timestamp=1700000010)
    for changed_scope in (
        scope(headers, method="POST"),
        scope(headers, path="/api/auth/me"),
    ):
        with pytest.raises(ValueError):
            verified_client_ip(changed_scope, KEY, timestamp=1700000010)
    with pytest.raises(ValueError):
        verified_client_ip(scope(headers), KEY, timestamp=1700000061)
    duplicate = scope(headers)
    duplicate["headers"].append((b"x-protocolguard-client-ip", b"198.51.100.6"))
    with pytest.raises(ValueError):
        verified_client_ip(duplicate, KEY, timestamp=1700000010)
    assert verified_client_ip(scope(headers), "", timestamp=1700000010) is None
    assert verified_client_ip(scope({}), KEY, timestamp=1700000010) is None
    mapped = signed("::ffff:203.0.113.15", timestamp=1700000000)
    assert (
        verified_client_ip(scope(mapped), KEY, timestamp=1700000010) == "203.0.113.15"
    )


def test_two_verified_networks_record_separate_addresses_and_enforce_the_correct_ip(
    tmp_path,
):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/ips.db",
            ml_enabled=False,
            client_ip_signing_secret=KEY,
            ip_auto_restrict_enabled=False,
        )
    )
    with (
        TestClient(app, client=("192.0.2.200", 5000)) as first,
        TestClient(app, client=("192.0.2.200", 5000)) as second,
    ):
        seed(app.state.session_factory, "bank-test-password", "admin-test-password")
        for client, address, username in (
            (first, "203.0.113.15", "demo01"),
            (second, "198.51.100.25", "demo02"),
        ):
            login = client.post(
                "/api/auth/login",
                headers={
                    **signed(address, "POST", "/api/auth/login"),
                    "x-forwarded-for": "203.0.113.99",
                },
                json={"username": username, "password": "bank-test-password"},
            )
            assert login.status_code == 200
            assert (
                client.get("/api/bank/balance", headers=signed(address)).status_code
                == 200
            )
        with app.state.session_factory() as db:
            assert set(db.scalars(select(SecurityEvent.ip))) == {
                "203.0.113.15",
                "198.51.100.25",
            }
        from test_blocking import admin_login

        headers = admin_login(second)
        response = second.post(
            "/api/admin/ips/block",
            headers=headers,
            json={
                "ip_address": "203.0.113.15",
                "confirmed": True,
                "note": "Verify signed network enforcement",
            },
        )
        assert response.status_code == 200
        assert (
            first.get("/api/bank/balance", headers=signed("203.0.113.15")).status_code
            == 403
        )
        assert (
            second.get("/api/bank/balance", headers=signed("198.51.100.25")).status_code
            == 200
        )
        tampered = signed("198.51.100.25")
        tampered["x-protocolguard-client-ip"] = "203.0.113.99"
        assert second.get("/api/bank/balance", headers=tampered).status_code == 400
        with app.state.session_factory() as db:
            assert "203.0.113.99" not in set(db.scalars(select(SuspiciousIP.address)))


def test_short_signing_secret_fails_without_disclosing_it(tmp_path):
    with pytest.raises(ValueError, match="at least 32 bytes") as error:
        create_app(
            Settings(
                database_url=f"sqlite:///{tmp_path}/test.db",
                client_ip_signing_secret="short-secret",
            )
        )
    assert "short-secret" not in str(error.value)


def test_required_forwarding_blocks_unsigned_api_and_direct_websocket_bypass(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/strict.db",
            ml_enabled=False,
            client_ip_signing_secret=KEY,
            require_signed_client_ip=True,
        )
    )
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert (
            client.get(
                "/api/auth/me", headers={"x-forwarded-for": "203.0.113.15"}
            ).status_code
            == 400
        )
        assert (
            client.get(
                "/api/auth/me", headers=signed("203.0.113.15", path="/api/auth/me")
            ).status_code
            == 401
        )
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/admin/events"):
                pass
        assert error.value.code == 4403
    with pytest.raises(ValueError, match="requires CLIENT_IP_SIGNING_SECRET"):
        create_app(
            Settings(
                database_url=f"sqlite:///{tmp_path}/missing.db",
                require_signed_client_ip=True,
            )
        )
