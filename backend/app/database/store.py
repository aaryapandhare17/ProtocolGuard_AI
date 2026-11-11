from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# One transaction-scoped PostgreSQL lock preserves the same serialized security
# updates as SQLite BEGIN IMMEDIATE. It also works with transaction poolers.
SECURITY_LOCK_ID = 736482910


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def database_url(value):
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


def begin_security_transaction(db):
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    elif db.bind.dialect.name == "postgresql":
        db.connection().exec_driver_sql(
            f"SELECT pg_advisory_xact_lock({SECURITY_LOCK_ID})"
        )


def configure(value):
    url = database_url(value)
    if url.get_backend_name() == "sqlite":
        engine = create_engine(
            url, connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(engine, "connect")
        def pragmas(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
    else:
        engine = create_engine(
            url,
            connect_args={"connect_timeout": 15, "prepare_threshold": None},
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=300,
        )
    return engine, sessionmaker(engine, expire_on_commit=False)
