# Final feature validation

Validation performed on 11 November 2026 for the completed simulation-lab feature.
The next deployment change adds its own production-path checks.

| Area | Verified behavior |
| --- | --- |
| Authentication | Role isolation, hashed credentials/tokens, expiry, revocation, CSRF and throttling |
| Banking | Persistent dummy-account actions, validated transfer requests, protected endpoints |
| FSM | Transition table, invalid events, versioned evidence and read-only recorded replay |
| ML | Grouped synthetic data, normal-only IF fit, saved-model contract, prefix inference and evaluation |
| Risk/enforcement | Per-user evidence, decay, threshold block, session revocation and recovery |
| IP security | Independent addresses, shared-IP associations, gateway denial, expiry and recovery |
| Admin | Authenticated projections, persisted settings/audits, live events and evidence |
| Analytics | Provenance validation, same-cohort comparison, missing-artifact and policy-mismatch states |
| Simulation | Six scenarios, ten actors, isolation, persistence, admission limits and revoked admin access |

Executed checks:

- `python -m pytest backend/tests -q`: **112 passed**.
- `npm test`: **18 passed** across the two frontends.
- `npm run build`: both production frontend builds passed.
- Real Chromium lab workflows: confirmation gating, normal and rapid sessions,
  repeated login failures, actual models, saved-run reload and mobile layout.
- Source overview unchanged by isolated simulation execution. Backend tests compare
  source user balances/risk/block state and event/block/IP/alert table counts.
- Actual-model failed-login run: two demo actors, two account blocks, two IP
  restrictions and four sandbox alerts. Normal run: ten successful requests,
  no blocks or restrictions. Rapid browsing stayed below the configured threshold.

The backend emitted a dependency deprecation warning about FastAPI's TestClient
HTTPX integration; no test failed. Browser results and counts describe this executed
run, not promises of identical timing/scores on every host.

Previous feature checks also exercised desktop/mobile banking and admin workflows,
live WebSocket delivery, account/IP block and recovery, FSM playback and evaluation
filter changes. Rerun the automated tests after any code/dependency changes.

For presentation use [the walkthrough](demo-walkthrough.md) and
[the viva guide](viva-guide.md). For production setup use [the deployment guide](deployment.md).

## Deployment verification

The Render deployment change passed **116 backend tests** and **18 frontend tests**.
The Docker multi-stage build completed, including real 10,000-session synthetic data
creation, model training and a matching comparison report. Both compiled frontends
were tested from that image through local HTTPS using `npm run test:deployment`.
This verified secure admin cookies, bank actions and unchanged dummy balances,
server-side account block/session denial/recovery, WebSocket alert delivery, real
model reports, `/admin/` routes and deep-link reloads, the production simulation
execution guard and mobile overflow. This is container validation; it is not a
claim that a public Render service has already been created.

After restarting the validation container, the attached volume retained all ten
users, the administrator, 21 security events, two audit entries and one block-history
record. The health endpoint passed after restart. Hosted proxy/IP verification and
public Render reachability still require the actual Render service.

## Railway + Vercel verification

The split-hosting change passed **117 backend tests**, **20 frontend tests** and
**three API bridge tests**. Both SPAs built into the Vercel output with Admin's
`/admin/` base and the authenticated polling transport. The Railway API-only Docker
image built its own 10,000-session dataset, RF/IF artifacts and matching comparison
report, then passed its health check.

A local HTTPS preview exercised the actual Vercel API function against that separate
Railway image. `test:deployment` passed in polling mode: cookies/login, CSRF-protected
transfer with unchanged balance, account block and denied old session, polled block
event delivery, unblock/fresh login, measured reports, admin deep-link reloads,
production lab denial and mobile layout. This verifies the prepared split locally;
public deployment still requires the owner's Railway/Vercel account setup and URLs.

## No-card deployment verification

The PostgreSQL/free-tier change passed **121 backend tests**, including actual
PostgreSQL 16 schema, authentication, concurrent-user and restriction-history checks,
plus **20 frontend tests** and **four API-bridge tests**. PostgreSQL tests use isolated
schemas on a dedicated local/CI database, not a real Neon account.

A local HTTPS Vercel-style preview exercised the actual API bridge against FastAPI
with PostgreSQL and real models. The deployment browser check passed login/cookies,
CSRF-protected actions, dummy balance preservation, block/denial/recovery, polled
events, saved-model reports, admin deep links, the production lab guard and mobile
layout. Ten users, one administrator, 21 events and two audits survived a backend
restart without provisioning again.

The PostgreSQL Docker image built successfully, including the driver, generated
10,000-session synthetic dataset, trained detectors and matching comparison report.
The default Blueprint now explicitly selects `plan: free` and has no disk.
The proxy also handles a non-JSON hosting wake-up page as a retryable JSON error.

Render/Neon free-plan terms and Hugging Face's Docker/networking restrictions were
checked against their official documentation on 11 November 2026; links are in
[the no-card guide](free-deployment.md). Public deployment, real Neon connectivity
and account-specific signup requirements still need the owner's account setup.
