# Administrative monitoring APIs

All routes below require a verified administrator session. Ordinary banking cookies cannot
authorize them. Responses explicitly project supported fields rather than serializing ORM
objects, so password hashes, session cookies, and CSRF tokens are never returned in monitoring
data. Session references in event records are opaque stored digests, not usable credentials.

## Read endpoints

| Route | Data |
| --- | --- |
| GET /api/admin/overview | Registered users, active banking sessions, analyzed events, effective-risk distribution, account/IP blocks, alerts in the last 24 hours, hourly activity, recent incidents and ML availability |
| GET /api/admin/users | Searchable account summaries with effective/stored risk and status |
| GET /api/admin/users/{id} | Account summary, observed IP associations, and latest 100 security events |
| GET /api/admin/events | Bounded chronological security event history with persisted assessment/FSM status |

User lists accept literal username substring `q` (up to 80 characters), `offset`, and `limit`
(default 50, maximum 100). `%` and `_` are escaped rather than treated as search wildcards.
Event history accepts `q`, `user_id`, `after_id`, `before_id`, and `limit` (maximum 200).
Events return newest first. Query values are validated and SQL queries are parameterized.

Overview risk counts use time-decayed effective risk. Stored event assessments retain their
historical score. Active-session counts exclude revoked/expired sessions and admin sessions.
Analyzed-event counts exclude administrative risk-reset snapshots. They count detection
events, not unique HTTP requests; one request can produce multiple security events.
Activity and incident data come from the database, not synthetic training files. Empty time
buckets are zero. IP restriction counts honor expiration even before lazy release is recorded.

Events identify a known bank account or admin account where its stored association exists;
unknown requests remain unattributed. A named account in a failed-login event is an attempted
identifier, not proof of successful authentication. Outcomes and scope remain visible.

## Event streaming

The existing authenticated `/ws/admin/events` endpoint now accepts an optional
`after_event_id`. Supplying it opts into committed security-event delivery:

```json
{"type":"events","events":[{"id":101,"event_type":"VIEW_BALANCE"}],"event_cursor":101}
```

The full event objects have the same projection as the REST history endpoint. Messages are
ordered by event ID and batched at 100 rows. Cursor comparison is strict (`id > cursor`).
Reconnect with the last `event_cursor` to avoid replaying already received events. Initial
REST history followed by its highest event ID covers the gap before opening the socket.

Account alerts (`after_id`) and IP alerts (`after_ip_id`) retain independent cursors. Existing
clients that omit `after_event_id` continue to receive only alert channels. Administrator
revocation, expiry, origin validation and IP restrictions apply to the stream. The browser
client deduplicates event IDs and bounds its visible buffer to 200 events.

The dashboard uses these APIs together with the previously implemented risk, account block,
IP, alert, security settings and audit APIs. All mutating controls retain CSRF protection,
explicit confirmation, review-note validation, and audit logging.
