# Hybrid risk scoring

## What is implemented

Banking security events now produce persisted detection assessments. Events attributable
to a known account also produce append-only risk snapshots and update `users.risk_score`.
The event, analytical FSM transition, assessment, and user snapshot share the same SQLite
transaction. Failed API requests still retain their security evidence.

This feature calculates scores; it does not automatically block accounts or create alerts.
Those enforcement steps are the next feature. A risk score is an index, not a percentage
probability that an account owner is malicious.

## Formula

Each evidence component is between zero and one. Default assessment points are:

```text
assessment = 30 × FSM evidence
           + 35 × Random Forest score
           + 10 × Isolation Forest anomaly evidence
           + 25 × behavioral evidence

retained = previous_score × 2 ^ (−elapsed_seconds / 600)
current_score = max(assessment, retained)
```

Scores are bounded to 0–100. Repeating the same assessment does not add it to the previous
score. A previous spike instead halves after ten minutes without fresh evidence. The
latest persisted snapshot provides its timestamp. Read-only API responses calculate the
current effective score even while the account is inactive; `stored_score` remains the
last assessment snapshot, and `effective_score` includes decay since that assessment.
New activity persists the newly calculated score. There is no automatic unblock implied by decay.

Levels are low below 30, monitoring from 30 through 60, and high above 60. These levels do
not enforce access in this feature.

For example, FSM=1, RF=0.8, IF evidence=0.6, and behavior=0.4 contribute 30+28+6+10=74 points.
Repeating those components keeps the assessment at 74 instead of accumulating to 148.
With no new evidence, a stored score of 80 becomes 40 after one half-life.

## Evidence sources

**FSM:** A current invalid transition or transition into BLOCKED contributes one. Other
transitions contribute zero. Authentication and authorization remain independent of analysis.
Previously rejected states preserve their violation evidence through the existing rejecting sink.

**Random Forest:** Uses its numeric class score, not its binary classification. A validation
threshold such as 0.0125 can classify an observation as suspicious while contributing only
0.4375 weighted risk points. Thresholds and component weights serve different purposes.

**Isolation Forest:** Uses the persisted inference service's bounded upper-tail evidence:
`clip((normal_reference_percentile−0.95)/0.05, 0, 1)`. Raw anomaly scores are never used as
probabilities or directly multiplied into the final risk. Its default weight is limited
to ten points, reflecting the measured standalone false-positive behavior.

**Behavior:** Uses a rolling 60-second window for the known account. The largest factor
is the behavioral component; the factors are not added together:

| Indicator | Factor |
| --- | --- |
| Failed logins | `clip((count−2)/6, 0, 1)` |
| Transfer requests | `clip((count−3)/12, 0, 1)` |
| Unauthorized requests | `clip(count/3, 0, 1)` |
| Request burst | `clip((rate−5)/20, 0, 1)` only when at least ten requests were observed |
| Rate-limit event | 1 if present, otherwise 0 |

Logical request counts exclude paired LOGIN_SUCCESS/LOGIN_FAILED/TRANSFER_RECORDED events.
Rate divides that count by the observed span with a one-second denominator floor. This
is a bounded approximation without request IDs. Threshold constants are documented policy
choices for the demo; weights, observation limits, window, and half-life are configurable.

## ML observations

Models load once at application startup from the trusted local directory configured by
`ML_MODEL_DIRECTORY`. Banking observations use the same extractor, feature schema, and
saved artifact contract as training.

Two ML contexts are supported:

- The current session's ordered trace, after at least four events. It must retain its
  initial LOGGED_OUT → LOGIN_ATTEMPT prefix and fit within the configured event limit.
- A recent failed-login window, once at least three failed attempts are recorded for the
  account. Complete LOGIN_ATTEMPT/LOGIN_FAILED pairs are selected across their separate
  revoked attempt sessions. This matches the generator's failed-login sequences without
  combining concurrent authenticated sessions into one fabricated session.

The RF and normalized IF components each take their maximum across available contexts.
Their source contexts and event IDs are stored alongside the predictions. Session ML
uses the bounded full session, while behavioral indicators and failed-login aggregation
use the rolling time window. A previously detected session violation can remain evidence
while that same session continues; decay is not a way to erase an actively repeated violation.

Oversized or historically incomplete sessions are skipped for ML with an explicit reason.
Behavioral windows keep only the latest event limit and mark truncation. This avoids
unbounded inference work and avoids pretending that a mid-session suffix is a training prefix.

Missing/disabled/incompatible models and inference failures have explicit status fields.
Available FSM and behavioral evidence still persists; missing model contributions are zero.
Weights are **not** renormalized to pretend full detector coverage. With default weights,
FSM plus behavioral evidence can contribute at most 55 points to a new assessment when
both ML components are unavailable; retained historical risk can still be higher. Inference exceptions do not discard the original banking event.

## Attribution and IP independence

Known-user scores are keyed by user ID, never by IP. Concurrent users sharing a connection
address keep independent windows and histories. Failed-login attempts can be attributed to
an existing username without claiming the caller authenticated as that account owner.
Requests with no identified account receive an `unattributed_event` assessment, but do not
create a user risk snapshot. Admin authentication events are outside the banking risk pipeline.

An event's source IP remains in the security log, but it is not used to copy account risk
onto other accounts or an IP-level score. Separate suspicious-IP scoring and enforcement
will be implemented in their own feature.

## Persistence and administrator APIs

The startup schema creation adds two tables without resetting existing databases:

- `detection_results`: one assessment per banking event, uniquely linked to its event.
  JSON evidence includes policy version/weights, individual contributions, ML predictions
  and statuses, behavioral counts, window event IDs, previous/decayed scores, and reasons.
- `risk_scores`: known-account snapshots linked to assessments, with previous/new score
  and timestamp. Older assessments and snapshot evidence are preserved.

SQLite BEGIN IMMEDIATE transactions serialize concurrent read/modify/write operations so
one request cannot overwrite another's risk update. Existing events are not retrospectively
rescored on startup, and an unchanged historical snapshot keeps its original policy evidence.

Read-only administrator endpoints require a verified admin session:

- `GET /api/admin/risk/policy`: current weights and limits, startup model status, and explicit
  `automatic_blocking: false` and `ip_risk_included: false` flags.
- `GET /api/admin/users/{id}/risk?limit=50`: effective/stored scores, assessment timestamp,
  and the latest snapshot evidence. History limit is bounded to 1–200.

No unauthenticated or ordinary banking caller can read these endpoints. Use administrator
login in `/docs` for now; admin dashboard visualization is a later feature.

## Configuration and checks

See `.env.example` for `ML_ENABLED`, `ML_MODEL_DIRECTORY`, `RISK_FSM_WEIGHT`, `RISK_RF_WEIGHT`,
`RISK_IF_WEIGHT`, `RISK_BEHAVIOR_WEIGHT`, `RISK_WINDOW_SECONDS`, `RISK_HALF_LIFE_SECONDS`, and
`RISK_MAX_EVENTS`. Weights must be finite, bounded, and sum to one. Change environment
configuration and restart the backend to apply it. New snapshots retain the new policy;
read-time decay uses the currently configured half-life. Existing training commands do
not require the models to be enabled in the banking backend.

Tests cover hand-calculated contributions, level boundaries, nonaccumulation, half-life
decay, malformed policies, bounded windows, account/IP independence, failed-login grouping,
anonymous/admin isolation, missing/broken models, real saved-model parity, API authorization,
and concurrent assessment preservation.
