# PostgreSQL and Neon support

Local development continues to use SQLite. Hosted deployments can use PostgreSQL:

```sh
python -m pip install -e 'backend[postgres,ml]'
```

Store the database connection string in the hosting platform's private `DATABASE_URL`
secret. Neon supplies a `postgresql://...` URI including TLS options; copy it without
removing those options. The application normalizes `postgres://` and `postgresql://`
to the psycopg 3 SQLAlchemy driver without changing the password or query parameters.
Do not commit, paste into chat or print a real database connection string.

The connection pool is bounded to two reusable connections plus two overflow
connections. Liveness checks and recycling handle disconnected/suspended endpoints.
Automatic prepared statements are disabled for transaction-pool compatibility.
The app uses transaction-scoped PostgreSQL advisory locks to serialize security
updates, matching the existing SQLite transaction boundary. Locks are released on
commit/rollback; there is no session-level lock to leak through a pooler.
This preserves individual risk/session updates and enforcement consistency, with a
coarse serialization cost appropriate to this small academic service.

Account-block and IP-restriction uniqueness indexes have PostgreSQL partial-index
predicates. A released historical restriction therefore permits a later active
restriction on the same entity. Denied requests still commit their security
evidence, and all timestamps remain UTC.

`REQUIRE_POSTGRES=true` makes the hosting entrypoint reject a SQLite fallback.
This prevents accidental use of an ephemeral file when a database secret is missing.
SQLite files are not automatically imported. A fresh Neon project starts with a
fresh schema and explicit demo provisioning. Existing incompatible PostgreSQL
schemas need a reviewed migration; `create_all` does not rewrite existing indexes.

## Tests

`backend/tests/test_postgres.py` includes driver/TLS-option normalization, compiled
partial-index checks and the external-database startup guard. With
`PROTOCOLGUARD_TEST_POSTGRES_URL` set, it also tests actual PostgreSQL login,
concurrent independent users, persisted banking events, repeated account block and
recovery, and repeated IP restriction history.

Integration tests create and remove uniquely named test schemas. They do not drop
existing application tables. Use a dedicated local/CI PostgreSQL database with
schema-creation permission; do not run this against a live customer database.
GitHub Actions supplies a temporary PostgreSQL 16 service for these checks.
