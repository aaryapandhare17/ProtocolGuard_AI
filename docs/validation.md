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
[the viva guide](viva-guide.md). For production setup use the deployment guide.
