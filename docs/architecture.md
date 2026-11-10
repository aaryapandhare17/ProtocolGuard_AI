# Architecture and implementation plan

SecureBank (port 5173) and ProtocolGuard Admin (port 5174) are separate React apps.
Both send /api requests through their Vite development proxy to FastAPI (8000).
SQLite persists users, sessions, security events, detection evidence, and risk histories.
Block records, alerts, and audit logs are planned in the enforcement features.
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
See [hybrid risk documentation](hybrid-risk.md). Account blocking and alerts are next.
SQLite write transactions are serialized with BEGIN IMMEDIATE to avoid lost updates.

Planned event path: verified session → banking action → persisted security event →
analytical DFA and ML inference → hybrid risk evidence → backend block policy → admin WebSocket update.
Authorization remains independent of the analytical DFA. Account and IP risk remain separate.
Training uses reproducible synthetic sessions; reported metrics must come from executed evaluation.

Feature sequence: foundation; authentication and banking UI; event collection and DFA;
ML generation/training/evaluation; risk and blocking; admin UI and WebSockets;
isolated simulations, end-to-end validation, and learning documentation.

Production will require HTTPS, explicit CORS origins, deployment-specific proxy trust,
secure session configuration and secrets provided through environment settings.
The Vite proxy is for development. No real payment integrations are planned.
