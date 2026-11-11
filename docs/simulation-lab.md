# Controlled simulation lab

Open **Simulation lab** in ProtocolGuard Admin after provisioning the demo accounts.
Select one of six fixed scenarios, one to ten available demo actors, a plan seed and
an audit note, then confirm the isolated scope and choose **Run simulation**.
The page records actual responses and detector decisions; a scenario name does not
guarantee a block. Decisions depend on the current models, thresholds and execution timing.

| Scenario | Executed behavior |
| --- | --- |
| Normal banking session | Login, balance, history, one dummy transfer and logout |
| Repeated login failures | Bounded invalid credentials, throttling and a protected-access probe |
| Unauthorized balance access | Balance requests without a verified session |
| Rapid request bursts | Authenticated balance/history requests with bounded concurrency |
| Abnormal transfer requests | Repeated validated dummy transfer requests |
| Mixed suspicious behavior | Logout, revoked-session probes, renewed login and transfer activity |

Each actor performs at most 50 HTTP requests. A run uses at most four in-flight
requests; each server process admits at most two runs simultaneously. The default
uses a distinct virtual source IP per actor. The shared-IP option demonstrates how
network restrictions can affect several independent accounts.

## Isolation and execution

The runner creates a disposable SQLite database and an isolated FastAPI application.
Only the selected demo usernames are copied; their balances, passwords, sessions,
risk histories and restrictions are created afresh. Random one-run credentials stay
in memory. The sandbox reuses the loaded RF/IF detector and snapshots the live risk
and enforcement policy. Its requests execute the real authentication, banking, FSM,
risk, account blocking and IP gateway handlers through HTTPX's in-process ASGI
transport. There are no external targets or arbitrary request paths.

Virtual addresses belong to the documentation-only 192.0.2.0/24 range. They describe
sandbox actors, not connections to other computers. Unauthorized requests do not gain
an invented account association. An account block and an IP restriction remain
separate outcomes. Missing ML evidence is labeled and may reduce detection.

The source database receives only simulation run records and administrator audit
entries. Source balances, accounts, bank sessions, security events, risk histories,
alerts and IP restrictions stay unchanged. Exported sandbox events have
`simulated: true` and appear in the lab's separate timeline. They do not enter the
live monitor, live prediction history or overview charts. Sandbox user/session/event
IDs are not links to live records.

After execution the disposable database is deleted. The saved result contains
request method/path/status traces, per-actor risk and restriction outcomes, event
snapshots, alert evidence, model availability, configuration and elapsed time.
It excludes passwords, raw session cookies and CSRF tokens. A fixed seed reproduces
the request plan, not exact timings or scores.

## Persistence and access

Runs are saved as `running`, `completed`, `completed_with_errors` or `failed`.
The lab polls active runs and lets administrators reopen saved results after reload
or a later server restart. Execution belongs to the current server process; it is
not a durable background job. An interrupted process cannot resume an unfinished run.
Leaving the page does not cancel execution while that process/request remains active.
The runner releases the live database transaction during sandbox execution, allowing
normal dashboard reads. Administrator session validity is rechecked before returning
completed results; a revoked administrator must sign in again to retrieve the saved run.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/simulation/scenarios` | Catalog, provisioned demo accounts and availability |
| `POST /api/simulation/run` | Execute one bounded run and save its result |
| `GET /api/simulation/runs?limit=25` | Recent run metadata and summaries |
| `GET /api/simulation/runs/{id}` | Saved configuration and complete result |

All endpoints require administrator authentication. Execution also requires CSRF,
`confirmed: true`, a 3–500 character review note, a fixed scenario name and unique
provisioned usernames from `demo01` through `demo10`. Unknown fields are rejected.
A full runner returns HTTP 409 instead of queueing an unbounded workload.
`SIMULATION_ENABLED=true` enables execution only when `PROTOCOLGUARD_ENV=development`.
Production execution is denied even if the flag is enabled; saved history remains
administrator-readable.

## Verification

Backend tests exercise every scenario against real handlers, isolated enforcement,
shared addresses, disabled models, ten simultaneous actors, saved-run persistence,
CSRF/authorization/validation, process admission limits, live reads during execution
and administrator revocation. Deterministic detector fixtures test enforcement
branches without pretending they are model evaluation results. Browser checks use
the saved real models and verify normal/rapid/failed-login runs, saved-result reload,
unchanged live overview values and mobile layout. Frontend tests check explicit
confirmation, request configuration and failure feedback.
