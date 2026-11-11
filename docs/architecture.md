# Architecture and implementation plan

SecureBank (port 5173) and ProtocolGuard Admin (port 5174) are separate React apps.
Both send /api requests through their Vite development proxy to FastAPI (8000).
SQLite persists users, sessions, security events, detection evidence, and risk histories.
Account blocks, security alerts, administrator audit logs, and risk-reset baselines are
also persisted. Independent IP observations, restrictions, associations, and alerts are
now persisted as well; see [IP security](ip-security.md).
The backend implements persistent demo accounts, separate administrator authentication,
HttpOnly sessions, CSRF validation, session expiration/revocation, login throttling,
and banking security events. A pure DFA now processes banking events in the same
transaction, preserving before/after states and versioned violation evidence.
Admin-only APIs expose the definition and persisted session replay; see [FSM documentation](fsm.md).
The ML package generates reproducible synthetic sessions and exports shared numeric features,
with grouped train/validation/test partitions and unseen held-out scenario families.
See [dataset documentation](ml-dataset.md). Random Forest and normal-only Isolation Forest
now train with partition-preserving prefixes; validated artifacts share the runtime feature
contract. Frozen thresholds support saved-model inference and independent reevaluation.
See [model documentation and measurements](ml-models.md). The event pipeline now computes
hybrid scores in the same transaction, retaining component evidence and decaying history.
See [hybrid risk documentation](hybrid-risk.md). Assessments above the persistent threshold
now block accounts and revoke sessions transactionally. Admin recovery APIs and committed
alert WebSocket delivery are implemented; see [account enforcement](account-blocking.md).
An ASGI gateway enforces IP restrictions before routes and protects WebSocket connections;
IP state remains independent of account state, with a development-only recovery CLI.
SQLite write transactions are serialized with BEGIN IMMEDIATE to avoid lost updates.

Implemented event path: verified session → banking action → persisted security event →
analytical DFA and ML inference → hybrid risk evidence → backend block policy → admin WebSocket update.
Authorization remains independent of the analytical DFA. Account and IP risk remain separate.
Training uses reproducible synthetic sessions; reported metrics must come from executed evaluation.

Feature sequence: foundation; authentication and banking UI; event collection and DFA;
ML generation/training/evaluation; risk and blocking; admin UI and WebSockets;
isolated simulations, end-to-end validation, and learning documentation.

Production will require HTTPS, explicit CORS origins, deployment-specific proxy trust,
secure session configuration and secrets provided through environment settings.
The Vite proxy is for development. No real payment integrations are planned.

The administrator frontend now consumes these real read APIs and authenticated streams.
See the [dashboard guide](admin-dashboard.md) and [API projection reference](admin-api.md).
It keeps separate page components, request/resource/live hooks, shared UI primitives and
confirmed mutations; chart-heavy pages are loaded lazily.

The lazily loaded FSM page uses React Flow for the backend-defined graph and advances
through persisted transition snapshots without issuing banking actions. See the
[visualizer guide](fsm-visualizer.md) for partial-history and acceptance semantics.

The ML analytics/comparison pages read verified saved reports and bounded persisted model
predictions. A separate CLI compares frozen detectors on identical observations without
fitting; synthetic evaluation stays separate from operational history. See [analytics](ml-analytics.md).

The [simulation lab](simulation-lab.md) runs the same banking pipeline in disposable
ASGI applications with separate SQLite databases. Only run snapshots and audit entries
are persisted in the source database; sandbox activity never enters live event tables.

The preferred split deployment uses one Vercel origin for both SPAs and a server-side
API bridge to Railway's API-only image. Host-only login cookies remain on Vercel;
no third-party cookie dependency is introduced. This build selects cursor-based
HTTP polling while local/direct deployments retain WebSockets. See
[Railway + Vercel](railway-vercel.md) for configuration and limitations.
