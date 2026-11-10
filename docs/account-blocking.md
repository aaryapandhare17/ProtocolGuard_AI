# Account blocking, security alerts, and recovery

## Automatic enforcement

After each known-account assessment is persisted, the backend reads the stored enforcement
settings. By default, a score **strictly above 60** automatically blocks the account.
Exactly 60 does not block. The trigger is a risk index, not a calibrated probability.

The same database transaction:

1. Sets the account's persistent blocked flag.
2. Creates one active block record containing the threshold, score, triggering event,
   assessment ID, component evidence, and reason.
3. Revokes every banking session for that account, including other browsers.
4. Adds BLOCK_ACCOUNT control markers with FSM transitions for those sessions.
5. Creates one high-severity security alert and an automatic-action audit record.

The triggering protected request returns HTTP 403 instead of protected data or a new login
cookie. Subsequent requests with a recognized blocked account's token also return 403,
even though the session is revoked. Existing SecureBank routing displays its restricted page.
Unknown tokens continue to receive 401. Normal session expiry and role/CSRF checks remain
independent of the analytical DFA.

An active-block uniqueness index and serialized SQLite writes prevent duplicate active
blocks/alerts under concurrent requests. Control markers reference the block; they do not
count as fresh weighted threat assessments, avoiding recursive scoring and enforcement.

Blocks persist across restarts. Risk decay does not unblock an account. A block targets the
account only: other users on the same IP and administrator sessions are unaffected.
No IP block is created by this feature.

## Administrator actions

All routes require an administrator cookie. Mutation routes also require the login response's
CSRF token in `X-CSRF-Token`, `confirmed: true`, and a nonblank note of 3–500 characters.
The API confirmation is ready for the later admin UI's confirmation dialogs.

| Route | Behavior |
| --- | --- |
| `POST /api/admin/users/{id}/block` | Manual account block and session revocation |
| `POST /api/admin/users/{id}/unblock` | Release account blocks; optionally reset current risk |
| `GET /api/admin/blocks?active=true&user_id=1` | Read block evidence/history; filters are optional |
| `GET /api/admin/alerts?unresolved=true` | Read persisted alerts |
| `POST /api/admin/alerts/{id}/resolve` | Resolve an alert without releasing the account block |
| `GET /api/admin/audit-logs` | Read automatic/admin action history |
| `GET /api/admin/settings/security` | Read the persistent enforcement policy |
| `POST /api/admin/settings/security` | Change threshold and automatic-blocking enablement |

List endpoints accept bounded `limit` values from 1–200.

Example mutation body (after admin login):

```json
{"confirmed": true, "note": "Reviewed the account activity"}
```

Unblock also accepts `reset_risk` (default true). Settings updates additionally require
`block_threshold` (0–100) and `auto_block_enabled` (boolean). Every mutation is audited,
including harmless repeated block/unblock actions. Repeated active blocks create no new
alert, while releasing and later blocking again creates a new historical block record.

Resolving an alert does not unblock its account. Unblocking resolves any still-open alerts
associated with the released blocks. No IP state is modified by either action.

## Fresh login and risk baseline

Unblock never reactivates an old session. A new login is required.

By default, unblock resets current account risk to zero and records an explicit
ADMIN_RISK_RESET event, detection snapshot, and risk-reset baseline. Earlier events, scores,
blocks, notes, and assessments remain intact. Subsequent rolling behavioral windows and
failed-login grouping exclude pre-reset events. This prevents stale attack evidence from
immediately undoing the administrator's review. Revoked-session traces are excluded from
ML inference, although denied requests still receive analytical evidence.

Using `reset_risk: false` deliberately preserves risk. If it still exceeds the enabled
threshold, the next assessed request can immediately block the account again. Repeating
unblock on an already-unblocked account is a no-op and cannot repeatedly erase new risk.

## Persistent settings and schema

New tables are `security_settings`, `blocked_entities` (account blocks), `security_alerts`,
`admin_audit_logs`, and `risk_resets`. Startup adds these tables without deleting existing
records. The database remains SQLite in this development stage.

`BLOCK_THRESHOLD=60` and `AUTO_BLOCK_ENABLED=true` initialize the singleton settings row
only when it does not exist. Later changes use the authenticated settings API and persist
across restarts; editing environment defaults does not overwrite an administrator's stored
policy. Disabling automatic blocking does not release existing blocks or disable manual blocks.

The default low/monitoring/high risk labels remain fixed bands. A custom enforcement threshold
can therefore block a score whose display band is monitoring. Account status and threshold
are distinct fields.

Banking and admin login throttles now use separate endpoint namespaces, so a banking failed-login
burst cannot consume the admin login budget needed for account recovery. IP restriction and
its separate development recovery mechanism remain a later feature.

## Live alert stream

`/ws/admin/events?after_id=0` requires an authenticated administrator cookie. Browser Origin
must be on the configured allowlist; ordinary banking cookies cannot authenticate this stream.
The backend rechecks session validity/revocation on every poll and closes invalid sessions
with code 4401. Untrusted origins receive 4403.

Messages:

```json
{"type":"connected","cursor":0}
{"type":"security_alerts","alerts":[{"id":1,"user_id":1,"block_id":1}],"cursor":1}
```

The actual alert objects include severity, reason, evidence, timestamps, and resolution state.
Alerts are read from committed database rows in batches of up to 100, polled every 250 ms;
uncommitted/rolled-back alerts are not broadcast. On reconnect, pass the last received cursor
as `after_id` to resume without replaying earlier IDs. Sending text `ping` receives `pong`.
HTTP reads provide updated resolution state; this first stream announces new alerts, not
arbitrary security events or later edits to existing alerts.

The admin Vite server proxies `/ws` with WebSocket support. The later admin dashboard will
consume this channel; its UI is still the existing foundation page.

## Checks

Executed tests cover threshold equality and exceeding it, persistent/configurable settings,
automatic enablement, denial of the triggering request, all-session revocation, shared-IP
independence, duplicate manual and automatic requests, confirmed/CSRF-protected admin controls,
unblock/reset/fresh-login behavior, preserved history, independent alert resolution, live
committed alerts, reconnect cursors, origin rejection, and administrator logout closing streams.
A Chromium workflow also verified the restricted page, live alert, unblock, old-cookie denial,
and fresh login against a running backend with real models loaded.
