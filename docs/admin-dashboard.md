# ProtocolGuard administrator dashboard

## Start and sign in

Start the backend with `python -m app.run --reload --port 8000`, then run
`npm run dev:admin` from the repository root. Open http://localhost:5174.
Use the provisioned `admin` account and the password chosen with `DEMO_ADMIN_PASSWORD`
during `python -m app.seed`; there is no password embedded in the frontend.
Run SecureBank separately at http://localhost:5173 to create actual banking activity.

The UI verifies administrator authentication before mounting the workspace. It uses
HttpOnly session cookies and a CSRF token in sessionStorage for protected writes. Reloads
in the same tab retain the CSRF token; a new tab without it asks the administrator to sign
in again. Logout revokes the admin session and unmounts the monitoring connection.

## Available pages

| Page | Live backend behavior |
| --- | --- |
| Overview | Six real metric cards, 24-hour event activity, effective-risk distribution, incidents, latest events and detector availability |
| Live monitoring | Committed security events with account/admin identity, IP, action, historical risk, outcome, filtering, pause/resume and reconnect handling |
| Users | Username search, bounded pagination, independent effective risk, active/blocked status and confirmed account controls |
| User detail | Observed IPs, risk history, assessment reasons and raw evidence, recent FSM transitions, event timeline and block history |
| Suspicious IPs | Suspicious/restricted addresses, optional benign observations, account associations, independent IP risk, manual restrict/unblock controls |
| IP detail | Current restriction, expiry, evidence, restriction history and network event history |
| FSM visualizer | Eight-state React Flow graph, persisted transition replay, invalid-edge highlighting, seek/play/pause controls and formal transition reference |
| Security alerts | Account and IP incidents, unresolved/history views, evidence inspection, account-alert resolution and IP release |
| ML analytics | Saved RF/IF metrics, confusion matrices, feature importances, and separate recent live prediction history |
| Detector comparison | Verified same-cohort FSM/RF/IF/hybrid results, timing, frozen policy and provenance |
| Simulation lab | Six isolated scenarios, up to ten simultaneous demo actors, shared virtual IPs, saved traces and sandbox evidence |
| Settings | Confirmed persistent threshold/enablement changes, model availability, risk weights and administrator/system audit records |

The [simulation lab](simulation-lab.md) exports separately labeled sandbox results.
Model training statistics and sandbox activity are not mixed into the live overview.

## Security actions

Every block, unblock, alert resolution and settings change opens a native modal dialog.
The administrator must provide a meaningful review note and explicitly check confirmation
before the button is enabled. Cancel/Escape sends no mutation. The backend independently
checks role, CSRF, confirmation, input and notes; frontend controls are not authorization.

Unblock-account dialogs default to resetting current risk while preserving evidence and
requiring a fresh banking login. Resolving an account alert does not unblock its account.
IP dialogs explain shared-address effects and administrator self-lockout; optional duration
limits can be entered when restricting an address. IP and account actions remain independent.
An IP restriction affecting this connection replaces the workspace with a network-restricted
screen; recover from another unrestricted address or use the documented local recovery CLI.

A saved action refreshes the active data view and appears in the audit log. Errors remain
in the dialog with the review note intact, so an unsuccessful mutation is not shown as saved.

## Data and connections

See [admin API documentation](admin-api.md) for projections, counts, privacy, filters and
cursor semantics. The client opens one authenticated same-origin WebSocket for events,
account alerts and IP alerts, remembering all three cursors during reconnects. Event IDs
are deduplicated, and the visible live buffer is bounded to 200. Pause freezes only the
visible monitoring table; backend analysis and the shared connection continue.

The top bar reports actual connection state. Reconnect uses exponential delays from one
second up to fifteen seconds. Resource panels refresh every ten seconds; live events also
refresh from HTTP while the stream is unavailable. Initial REST history closes the startup
gap before the WebSocket opens. Session revocation/expiration returns the UI to sign-in.

Data requests are canceled when obsolete, and ordinary background refreshes retain displayed
data rather than clearing forms. New/empty databases show explicit empty states. Missing
models show their actual coverage state rather than a fabricated prediction. Old events
without supported assessment evidence show an unavailable risk marker, not a zero score.

Charts use Recharts with lazy-loaded chart pages, and the dashboard has a collapsible mobile
navigation drawer and horizontally scrollable tables. Timestamps render in the browser's
local timezone. All financial data is simulated; monitoring data is persisted backend activity.

## Development proxy configuration

Default admin Vite proxy targets are http://127.0.0.1:8000 for `/api` and
ws://127.0.0.1:8000 for `/ws`. Set `API_PROXY_TARGET` and `WS_PROXY_TARGET` in the shell before
starting Vite to use an alternate backend. Include the frontend origin in `CORS_ORIGINS`.
No server-side secret needs a `VITE_` variable or is embedded in the client bundle.

## Verification and screenshots

Executed checks cover API authorization, real aggregate counts, literal search, pagination,
sensitive-field exclusion, administrator event labels and event-stream reconnect cursors.
Frontend tests cover confirmation gating, cancellation, error preservation, CSRF headers,
authentication loss, IP denial and abort handling. Browser checks exercise login errors,
real overview values, account/IP controls, SecureBank denial/recovery, risk history, live
events, pause/resume, reconnect, alert history, persistent settings, audit notes, logout,
session reloads, and desktop/tablet/mobile navigation without root horizontal overflow.

For project screenshots, seed accounts and run a normal SecureBank session first. Capture:

1. Overview at a desktop viewport around 1440 pixels wide.
2. Users and one account's risk/evidence history.
3. Live monitoring while another browser performs a banking action.
4. A confirmed block's alert and the SecureBank restricted page.
5. A mobile view around 390 pixels wide with the navigation drawer fully closed.

Use only dummy accounts and never capture an entered password or CSRF/session token.

See the [FSM visualizer guide](fsm-visualizer.md) for recorded-session snapshots and replay controls.

See [ML analytics and comparison](ml-analytics.md) for saved report setup and interpretation.
