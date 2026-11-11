"""Optional integration tests run against an isolated schema, never live app tables."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.schema import CreateIndex
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.database.store import database_url
from app.main import create_app
from app.models.entities import BlockedEntity, IPRestriction, SecurityEvent, User
from app.seed import seed


def test_postgres_urls_and_partial_indexes():
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg://"):
        url = database_url(
            prefix
            + "name:pa%24%24@db.example/database?sslmode=require&channel_binding=require"
        )
        assert url.drivername == "postgresql+psycopg"
        assert url.password == "pa$$"
        assert (
            url.query["sslmode"] == "require"
            and url.query["channel_binding"] == "require"
        )
    for model in (BlockedEntity, IPRestriction):
        index = next(index for index in model.__table__.indexes if index.unique)
        assert "WHERE active IS TRUE" in str(
            CreateIndex(index).compile(dialect=postgresql.dialect())
        )


@pytest.fixture
def pg_app():
    value = os.environ.get("PROTOCOLGUARD_TEST_POSTGRES_URL")
    if not value:
        pytest.skip(
            "Set PROTOCOLGUARD_TEST_POSTGRES_URL for PostgreSQL integration checks"
        )
    root = database_url(value)
    assert root.get_backend_name() == "postgresql"
    schema = "protocolguard_test_" + uuid.uuid4().hex
    admin = create_engine(root)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    scoped = root.update_query_dict({"options": f"-csearch_path={schema}"})
    config = Settings(
        database_url=scoped.render_as_string(hide_password=False),
        ml_enabled=False,
        serve_frontends=False,
        protocolguard_env="production",
        cors_origins="https://frontend.example",
    )
    instance = create_app(config)
    try:
        with TestClient(instance, base_url="https://frontend.example"):
            seed(
                instance.state.session_factory,
                "postgres-bank-password",
                "postgres-admin-password",
            )
            yield instance
    finally:
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def signin(client, admin=False, username="demo01"):
    return client.post(
        "/api/admin/auth/login" if admin else "/api/auth/login",
        json={
            "username": "admin" if admin else username,
            "password": "postgres-admin-password"
            if admin
            else "postgres-bank-password",
        },
    )


def test_postgres_auth_banking_repeated_blocks_and_ip_history(pg_app):
    with (
        TestClient(pg_app, base_url="https://frontend.example") as admin,
        TestClient(pg_app, base_url="https://frontend.example") as bank,
    ):
        login = signin(admin, True)
        assert login.status_code == 200
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        assert signin(bank).status_code == 200
        assert bank.get("/api/bank/balance").status_code == 200
        assert admin.get("/api/admin/overview").status_code == 200
        action = {"confirmed": True, "note": "PostgreSQL lifecycle verification"}
        for _ in range(2):
            assert (
                admin.post(
                    "/api/admin/users/1/block", headers=headers, json=action
                ).status_code
                == 200
            )
            assert bank.get("/api/bank/balance").status_code == 403
            assert (
                admin.post(
                    "/api/admin/users/1/unblock",
                    headers=headers,
                    json={**action, "reset_risk": True},
                ).status_code
                == 200
            )
            assert bank.get("/api/bank/balance").status_code == 401
            assert signin(bank).status_code == 200
        with pg_app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(BlockedEntity)) == 2
        # Releasing a partial unique index must allow another restriction on the same IP.
        for _ in range(2):
            assert (
                admin.post(
                    "/api/admin/ips/block",
                    headers=headers,
                    json={**action, "ip_address": "192.0.2.90"},
                ).status_code
                == 200
            )
            assert (
                admin.post(
                    "/api/admin/ips/unblock",
                    headers=headers,
                    json={**action, "ip_address": "192.0.2.90"},
                ).status_code
                == 200
            )
        with pg_app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(IPRestriction)) == 2


def test_postgres_concurrent_sessions_keep_accounts_and_events_independent(pg_app):
    def actor(index):
        with TestClient(pg_app, base_url="https://frontend.example") as client:
            username = f"demo{index:02}"
            assert signin(client, username=username).status_code == 200
            assert client.get("/api/bank/balance").status_code == 200
            assert client.get("/api/auth/me").json()["username"] == username

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(actor, range(1, 5)))
    with pg_app.state.session_factory() as db:
        for user in db.scalars(select(User).where(User.id <= 4)):
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(SecurityEvent)
                    .where(
                        SecurityEvent.user_id == user.id,
                        SecurityEvent.event_type == "VIEW_BALANCE",
                    )
                )
                == 1
            )


def test_external_database_requirement_is_enforced_without_exposing_credentials():
    from app.deploy import validate_hosting

    config = Settings(
        protocolguard_env="production",
        serve_frontends=False,
        require_postgres=True,
        database_url="sqlite:///./temporary.db",
        cors_origins="https://frontend.example",
    )
    with pytest.raises(ValueError, match="external PostgreSQL"):
        validate_hosting(config, "")
    validate_hosting(
        config.model_copy(
            update={
                "database_url": "postgresql://user:private@db.example/db?sslmode=require"
            }
        ),
        "",
    )
