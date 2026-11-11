# ProtocolGuard AI

Intelligent Banking Intrusion Detection Using Finite-State Machines and Machine Learning.
A Theory of Computation project using simulated banking data only.

## Current implementation

Two React/Vite apps, Tailwind styling, FastAPI, environment configuration, and tests.
SecureBank has a responsive login page and authenticated dashboard with real balance,
activity history, simulated transfer requests, logout, and a restricted-access screen.
Persistent users, separate admin authentication, expiring/revocable sessions, CSRF protection,
login throttling, and authentication event records are implemented.
A deterministic banking-session FSM records versioned transitions and violations, with
admin-only definition and replay APIs. Reproducible synthetic session generation and a shared
90-feature ML extractor are implemented.
Random Forest and Isolation Forest training, saved-model inference, and measured evaluation
are implemented. Hybrid risk scoring now runs on banking events with persistent evidence
and time-based decay. Automatic account blocking, session revocation, persisted alerts,
admin recovery APIs, and an authenticated live alert stream are implemented.
Suspicious-IP tracking, independent IP controls, temporary restrictions, and local
recovery are implemented. The dark admin dashboard now provides verified login, overview charts, live monitoring,
account/IP management, alerts, risk histories, security settings, and audit logs.
Interactive FSM visualization and read-only recorded-session replay are implemented.
ML analytics and four-detector comparison now show measured synthetic evaluation and
separate live prediction history. The controlled simulation lab executes six local
scenarios with up to ten isolated demo actors and saved, labeled evidence.
Banking balances are seeded dummy data;
activity comes from persisted security events.

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
python -m app.run --reload --port 8000
```

In two additional terminals, from the repository root:

```sh
npm run dev:bank
npm run dev:admin
```

SecureBank: http://localhost:5173 · Admin: http://localhost:5174
API documentation: http://localhost:8000/docs · Health: http://localhost:8000/api/health
The admin dashboard reads authenticated monitoring APIs and a live event/alert stream.
SecureBank calls authenticated banking APIs.

## Checks

```sh
python -m pytest backend/tests
npm test
npm run build
```

## Environment variables

See `.env.example`: `PROTOCOLGUARD_ENV` identifies the environment;
`DATABASE_URL` selects the persistent database; `CORS_ORIGINS` is a comma-separated
allowlist. Run the backend from the repository root to load `.env` consistently.
Never commit `.env`, credentials, local databases, or generated model artifacts.

See [architecture](docs/architecture.md) for the event pipeline and implementation sequence.

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

## Banking workflow

Sign in to SecureBank with a provisioned demo account. Balance/history buttons fetch
backend data and record security events. Transfer requests validate a dummy recipient
and amount and persist a TRANSFER_REQUEST event without changing balances or making payments.
Logout revokes the session. CSRF tokens are held in sessionStorage; session cookies are HttpOnly.
Opening a session in a different browser tab may require signing in again for write actions.
Access restrictions are checked by the backend and have a dedicated frontend page.

For an alternate development backend, set `API_PROXY_TARGET` before starting SecureBank.
The default is http://127.0.0.1:8000. Include the actual frontend origin in CORS_ORIGINS.

## Finite-state analysis

See [the DFA definition, transition table, examples, and replay API](docs/fsm.md).
Banking events update independent session states and preserve violation evidence.
The FSM analyzes protocol order; verified sessions and backend authorization still control access.

## Generate the ML dataset

With the backend environment activated, from the repository root:

```sh
python -m app.ml.dataset --sessions 10000 --seed 42 --output ml/datasets/bank-v1
```

This creates ignored JSONL sessions, feature CSV, and a versioned manifest. Existing
outputs are never overwritten. See [dataset design and feature definitions](docs/ml-dataset.md)
for scenario labels, grouped partitions, held-out cases, reproducibility, and limitations.
See the model training commands below for actual evaluation.

## Train and evaluate the detectors

```sh
python -m pip install -e "backend[dev,ml]"
python -m app.ml.train --dataset ml/datasets/bank-v1 --output ml/artifacts/bank-v1
python -m app.ml.evaluate --dataset ml/datasets/bank-v1 --artifacts ml/artifacts/bank-v1 --output ml/evaluation/bank-v1.json
```

Use new output paths when repeating runs. [Model documentation](docs/ml-models.md)
explains prefix observations, threshold selection, inference, and measured limitations.
The [recorded evaluation](docs/ml-evaluation.json) includes test and held-out results;
these are synthetic-data measurements, not production accuracy claims.
ML-specific tests require the `ml` extra; without it those tests are skipped.

## Hybrid risk scoring

Banking events now persist FSM, ML, and behavioral evidence with per-user score histories.
See [the scoring formula, configuration, and admin APIs](docs/hybrid-risk.md).
Models load from `ML_MODEL_DIRECTORY` at startup; train them first for full ML coverage.
If models are unavailable, assessments explicitly show degraded coverage. Scores decay
while inactive and do not repeatedly add the same evidence. Enabled account enforcement
blocks scores above the persistent threshold (60 by default).

## Account enforcement and alerts

See [account blocking and recovery](docs/account-blocking.md) for automatic enforcement,
confirmed administrator block/unblock actions, persistent settings, alert APIs, and the
`/ws/admin/events` alert stream. Unblock requires a fresh login and resets current risk by
default while preserving historical evidence. Account blocks never block a shared IP.
Admin controls are available in the dashboard with confirmation dialogs and review notes.

## IP restrictions and local recovery

[IP security documentation](docs/ip-security.md) explains source-address trust, temporary
abuse restrictions, admin block/unblock APIs, IP alerts, and shared-address effects.
Account and IP restrictions remain independent. The development runner ignores forwarded
headers by default. If you restrict the shared local IP, use the documented development-only
`python -m app.recover_ip` command against the same database; there is no admin HTTP bypass.

## Admin dashboard

Open http://localhost:5174 and sign in with the provisioned administrator credentials.
See the [dashboard guide](docs/admin-dashboard.md) and [monitoring API reference](docs/admin-api.md)
for pages, security controls, live connection behavior, development proxies, and screenshot steps.
All metrics and charts come from persisted backend data. The [simulation lab](docs/simulation-lab.md) keeps its sandbox evidence separate from live monitoring.

## FSM visualizer

The admin sidebar now opens an interactive eight-state graph and recorded-session replay.
See [the visualizer guide](docs/fsm-visualizer.md) for playback, seeking, rejection highlighting,
partial-history behavior, user-detail links, and read-only guarantees.

## ML analytics and detector comparison

```sh
python -m app.ml.compare --dataset ml/datasets/bank-v1 --artifacts ml/artifacts/bank-v1 --output ml/evaluation/comparison-v1.json
```

The admin sidebar now opens measured model metrics, confusion matrices, feature importance,
recent operational predictions, and a same-cohort comparison of FSM/RF/IF/hybrid detectors.
See [analytics setup and interpretation](docs/ml-analytics.md) and the
[executed comparison report](docs/detector-comparison.json). Missing reports show an explicit
unavailable state. Evaluation commands do not retrain models or modify banking records.

## Controlled simulation lab

The admin sidebar opens six fixed scenarios using disposable copies of `demo01`–`demo10`.
Runs execute real handlers, support simultaneous actors and shared virtual IPs, and save
request traces, detector evidence and restriction outcomes without changing live bank records.
See the [lab guide](docs/simulation-lab.md) for scope, limits, APIs and development configuration.

## Presentation and validation

Use the [demo walkthrough](docs/demo-walkthrough.md), [viva guide](docs/viva-guide.md)
and [validation record](docs/validation.md) for the final project review.

## Deploy on Render

[Deploy this repository](https://render.com/deploy?repo=https://github.com/aaryapandhare17/ProtocolGuard_AI)
using the included Docker/Blueprint configuration. It serves the bank at `/` and
admin at `/admin/` with one API origin and a persistent disk. Read the
[deployment guide](docs/deployment.md) for private account provisioning, the paid
service/disk requirement, HTTPS, backups, proxy verification and browser smoke checks.
Production lab execution and unverified automatic IP restrictions are disabled;
account enforcement remains enabled.
