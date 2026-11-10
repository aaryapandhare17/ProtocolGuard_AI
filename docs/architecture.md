# Architecture and implementation plan

SecureBank (port 5173) and ProtocolGuard Admin (port 5174) are separate React apps.
Both send /api requests through their Vite development proxy to FastAPI (8000).
SQLite will persist users, sessions, events, detection evidence, blocks, and audit logs.
The backend implements persistent demo accounts, separate administrator authentication,
HttpOnly sessions, CSRF validation, session expiration/revocation, login throttling,
and authentication security events. Detection is the next stage.
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
