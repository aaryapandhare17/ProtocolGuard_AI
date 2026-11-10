# Suspicious IP tracking and independent restrictions

## What is implemented

The backend records canonical IPv4/IPv6 addresses, associated account identifiers, security
events, first/last observed times, suspicious counts, recent IP evidence, restrictions, and
audited admin actions. This is separate from account risk and account blocking.

An automatically blocked account does **not** block its IP. Releasing an account does not
release an IP restriction, and releasing an IP does not release a blocked account.
An IP restriction affects every caller sharing that address, including administrators.

## Trusted source addresses

Use the development runner from the repository root with the backend environment active:

```sh
python -m app.run --reload --port 8000
```

This starts Uvicorn with forwarding-header trust disabled. The application uses the ASGI
connection address, not arbitrary `X-Forwarded-For` or `Forwarded` headers. If invoking
Uvicorn directly, include `--no-proxy-headers` for the same default.

Addresses are canonicalized; IPv4-mapped IPv6 is normalized to IPv4. CIDRs, ports, zone
identifiers, and hostnames are rejected by admin controls. Non-network ASGI test clients
without numeric addresses are not treated as real IP observations.

In local development both Vite apps proxy to the backend, so ordinary browser traffic
usually shares `127.0.0.1`. Blocking it affects both local apps. Distinct-IP tests use real
numeric ASGI connection addresses, not spoofed headers. In a production reverse-proxy
setup, configure trust explicitly only for controlled proxy addresses and ensure that
proxy strips client-supplied forwarding headers. The development runner does not enable
that trust automatically or pretend that a proxy's address is a customer's public IP.

## Evidence and temporary restrictions

IP evidence uses only LOGIN_FAILED, UNAUTHORIZED_REQUEST, and RATE_LIMIT_TRIGGERED events.
They represent failed/unauthorized operations; finding an existing username does not imply
the caller successfully authenticated. Account risk, BLOCK_ACCOUNT markers, and account
ACCESS_BLOCKED outcomes do not increase IP evidence or independently create IP restrictions.

The IP risk index is:

```text
min(100, 10 × failed_logins + 20 × unauthorized_requests + 15 × rate_limit_events)
```

Counts use the configured rolling time window and exclude events before the latest IP
release/expiry baseline. Queries keep at most the configured abuse threshold's number of
recent events. The index is not a probability, and it is not the account's hybrid score.
`risk_score` in IP API responses is recomputed for the current window; `stored_risk_score`
is the last observation snapshot. Lifetime suspicious counts remain available for review.

By default, **30 unauthenticated abuse events within 60 seconds** create one temporary
IP restriction lasting **120 seconds**. The trigger uses the event count, not the IP index.
The failed triggering request already receives its normal 401/429; subsequent requests
are denied by the gateway. Temporary expiry is checked on traffic or IP-detail/list reads,
which also record release, resolve the related alert, and reset the evidence baseline.
Old failures cannot immediately recreate an expired or administratively released block.

Settings are environment-based and apply on restart:

| Variable | Default |
| --- | ---: |
| IP_AUTO_RESTRICT_ENABLED | true |
| IP_ABUSE_THRESHOLD | 30 |
| IP_ABUSE_WINDOW_SECONDS | 60 |
| IP_RESTRICTION_SECONDS | 120 |

Disabling automatic restriction leaves observation and manual enforcement enabled; it does
not release existing restrictions. Unknown/failed login activity can affect legitimate
users sharing an IP, which is why temporary restrictions expire and manual review is separate.

## Gateway enforcement

An ASGI gateway checks restrictions before authentication and route handlers. A blocked
address receives HTTP 403 with `IP access restricted` on bank/admin APIs, docs, preflight,
and other backend routes. The only HTTP exception is `GET /api/health`. There is no admin
HTTP bypass. Blocked WebSocket handshakes close with 4403; existing admin streams recheck
their source address every poll and close when it is restricted.

Gateway denials create unattributed ACCESS_BLOCKED events with `scope: gateway`. They do
not mutate user sessions, user risk, or account block flags, and do not extend a restriction
through a feedback loop. Because IP restrictions do not revoke sessions, a still-valid
session can resume after IP release if its account is not separately blocked.

SQLite lookups and expiry writes run in worker threads with serialized transactions;
lock waits do not block the ASGI event loop. Active-restriction and IP/account-association
uniqueness constraints prevent duplicate concurrent records.

SecureBank's restricted page now distinguishes an account restriction from a network-address
restriction using the backend response, rather than describing every 403 as an account block.

## Administrator APIs

All routes require verified admin authorization. Writes require a CSRF header, explicit
`confirmed: true`, and a nonblank note of 3–500 characters.

| Route | Behavior |
| --- | --- |
| GET /api/admin/suspicious-ips | Suspicious/restricted IPs; `suspicious_only=false` includes benign observed addresses |
| GET /api/admin/suspicious-ips/{id} | Account associations, recent event history and restriction evidence |
| POST /api/admin/ips/block | Manual restriction, permanent unless a duration is provided |
| POST /api/admin/ips/unblock | Release only the IP restriction and reset its recent evidence baseline |
| GET /api/admin/ip-alerts | Persistent IP alert history |
| GET /api/admin/audit-logs | Shared administrator/system action history, including IP actions |

Lists/details accept bounded history limits of 1–200. A manual block can register an address
before its first observed request; its first-recorded timestamp then reflects that action.
Associated account IDs include known usernames from failed attempts, not proof of ownership.

Example block body:

```json
{
  "ip_address": "198.51.100.10",
  "confirmed": true,
  "note": "Reviewed repeated unauthenticated abuse",
  "duration_seconds": 120
}
```

Omit `duration_seconds` for a persistent manual block. Unblock accepts the same fields except
duration. The block response indicates `affects_current_connection` so a future admin UI can
explain self-lockout. Repeated block/unblock operations are audited no-ops rather than new
restrictions or new alerts. Independent account blocks and account risk are preserved.

## Safe local recovery

If a developer blocks the shared local address, run this **locally against the same database**:

```sh
python -m app.recover_ip --ip 127.0.0.1 --note "Reviewed local development restriction" --confirm
```

The command requires `PROTOCOLGUARD_ENV=development`, explicit confirmation and a meaningful
note. It acts through local database access, not a public recovery endpoint or a secret
bypass token. It releases only the named IP, preserves account restrictions, and records a
DEV_IP_RECOVERY audit entry. Production mode rejects the command. Health checks remain
available during lockout. Check `DATABASE_URL` and the working directory when recovering.

## Persistence and live alerts

New tables are `suspicious_ips`, `ip_accounts`, `ip_restrictions`, and `ip_security_alerts`.
They are added on startup without resetting existing data. Existing account-block tables
and alerts retain their original account-only meaning.

The authenticated `/ws/admin/events` stream now adds `ip_security_alerts` messages alongside
account alerts. IP alerts have a separate `ip_cursor`; reconnect using both `after_id` and
`after_ip_id`. The connected/pong messages include both cursors. Each IP alert contains its
address, restriction ID, reason, evidence, timestamps and resolution state. Alerts are read
only after database commit. The admin dashboard UI that consumes these APIs remains a later
feature; HTTP reads supply updated resolution state.

## Validation

Tests cover forged forwarding headers, IPv4/IPv6 normalization, source/event attribution,
multiple users on one IP, independent account/IP release, temporary expiry, disabled auto
restrictions, persistent records, concurrent deduplication and one-loop gateway requests,
confirmed/CSRF-protected admin controls, production recovery rejection, self-lockout recovery,
new/existing WebSocket denial, and IP alert reconnect cursors. A live Chromium check verified
network-specific restricted messaging, admin denial, forwarding-header denial, healthy status,
and recovery through the actual local CLI against a running backend.
