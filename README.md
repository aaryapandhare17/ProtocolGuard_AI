# ProtocolGuard AI

Intelligent Banking Intrusion Detection Using Finite-State Machines and Machine Learning.
A Theory of Computation project using simulated banking data only.

## Current implementation

Initial monorepo foundation: two responsive React/Vite apps, Tailwind styling,
a FastAPI health endpoint, environment configuration, and foundation tests.
Persistent users, separate admin authentication, expiring/revocable sessions, CSRF protection,
login throttling, and authentication event records are implemented.
FSM, ML, automated blocking, and live monitoring are planned;
the initial pages deliberately show development status instead of fabricated banking data.

## Requirements

Node.js 22.12+ (or 24), npm 11, Python 3.11+.

## Run locally

From the repository root:

```sh
npm ci
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e "backend[dev]"
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

In two additional terminals, from the repository root:

```sh
npm run dev:bank
npm run dev:admin
```

SecureBank: http://localhost:5173 · Admin: http://localhost:5174
API documentation: http://localhost:8000/docs · Health: http://localhost:8000/api/health
Both apps display the result of a real backend health request.

## Checks

```sh
python -m pytest backend/tests
npm test
npm run build
```

## Environment variables

See `.env.example`: `PROTOCOLGUARD_ENV` identifies the environment;
`DATABASE_URL` reserves the planned persistence URL; `CORS_ORIGINS` is a comma-separated
allowlist. Run the backend from the repository root to load `.env` consistently.
Never commit `.env`, credentials, local databases, or generated model artifacts.

See [architecture](docs/architecture.md) for the planned event pipeline and implementation sequence.

Full requirements: [project brief](docs/project-brief.md).

## Provision development accounts

Choose two different passwords, each at least 12 characters. Set `DEMO_USER_PASSWORD`
and `DEMO_ADMIN_PASSWORD` in your shell, then run `python -m app.seed` with the
virtual environment activated. On PowerShell use `$env:DEMO_USER_PASSWORD = "your chosen value"`
and `$env:DEMO_ADMIN_PASSWORD = "a different chosen value"`.
On macOS/Linux use `export DEMO_USER_PASSWORD=...` and `export DEMO_ADMIN_PASSWORD=...`.
Do not put real passwords in Git. The command creates `demo01` through `demo10` and
an `admin` account; rerunning it does not replace existing passwords.

Authentication uses HttpOnly, SameSite=Strict cookies and session tokens hashed in SQLite.
POST requests with a session require the login response's CSRF token in `X-CSRF-Token`.
Sessions expire after two hours; logout revokes them. Production cookies require HTTPS.
Client IPs come from the connection, never arbitrary forwarded headers.
