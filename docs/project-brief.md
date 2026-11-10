# CODEX MASTER PROMPT — PROTOCOLGUARD AI

## YOUR ROLE

You are a senior full-stack software engineer, cybersecurity engineer, machine learning engineer, and UI/UX designer.

Build a complete, functional, professional-quality college project named:

**ProtocolGuard AI — Intelligent Banking Intrusion Detection Using Finite-State Machines and Machine Learning**

This is a Theory of Computation project. The platform must demonstrate how finite-state machines, machine learning, and hybrid anomaly detection can identify suspicious banking application activity.

Do not build a static demonstration with hardcoded results. Build a working end-to-end application with real backend APIs, persistent database records, trained ML models, event monitoring, and security enforcement.

Work incrementally, test each feature, explain what was implemented, and commit completed features to GitHub.

---

# 1. PROJECT OVERVIEW

Build two separate websites connected to a shared Python backend.

### Website 1 — SecureBank

A minimalist, modern banking application.

Only two main pages are required:

1. Login page
2. Banking dashboard

Users must be able to log in, view a simulated balance, interact with banking action buttons, and log out.

Every relevant action must generate a backend security event.

Multiple users must be able to use the banking application simultaneously.

### Website 2 — ProtocolGuard AI Admin

A professional dark-themed cybersecurity monitoring dashboard.

The administrator must be able to:

- Monitor multiple users simultaneously.
- View individual threat scores.
- Inspect suspicious activity.
- View user IP addresses.
- Analyze FSM state transitions.
- View ML anomaly predictions.
- Receive live security alerts.
- Automatically block accounts when their risk score exceeds 60/100.
- Review suspicious IP addresses.
- Manually block and unblock accounts and IP addresses.
- View security event histories.
- Compare rule-based, ML-based, and hybrid detectors.
- Run controlled attack simulations.

The admin dashboard must show real backend data, not static placeholder information.

---

# 2. TECHNOLOGY STACK

Use the following stack unless there is a compelling technical reason to change it.

Frontend:
- React with Vite
- JavaScript
- Tailwind CSS
- React Router
- Lucide React icons
- Recharts
- React Flow
- Axios or Fetch API

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite for initial development
- WebSockets for real-time admin updates

Machine Learning:
- scikit-learn
- Pandas
- NumPy
- joblib
- Random Forest
- Isolation Forest

Testing:
- pytest
- FastAPI TestClient
- Vitest
- React Testing Library

Development:
- VS Code
- Git
- GitHub

Keep the architecture modular, readable, and maintainable.

---

# 3. PROJECT FOLDER STRUCTURE

Use a monorepo structure:

protocolguard-ai/

- apps/
  - securebank/
    - src/
      - components/
      - pages/
      - services/
      - hooks/
      - styles/
  - admin/
    - src/
      - components/
      - pages/
      - services/
      - hooks/
      - styles/
- backend/
  - app/
    - api/
    - core/
    - models/
    - schemas/
    - services/
    - security/
    - fsm/
    - ml/
    - websocket/
    - database/
  - tests/
- ml/
  - datasets/
  - training/
  - evaluation/
  - artifacts/
- scripts/
- docs/
- README.md
- .env.example
- .gitignore

You may improve the internal organization if necessary.

Keep trained model artifacts and generated datasets out of Git when they are large or reproducible.

---

# 4. UI/UX DESIGN REQUIREMENTS

The design must be minimalist, premium, polished, responsive, and consistent.

Avoid excessive gradients, neon colors, glassmorphism, crowded dashboards, unnecessary animations, and generic-looking templates.

Use generous whitespace, clean typography, subtle borders, consistent spacing, and carefully chosen accent colors.

## SECUREBANK DESIGN

Theme: Light

Primary background: #FFFFFF

Secondary background: #F8FAFC

Primary text: #111827

Accent blue: #2563EB

Secondary accent: #0F766E

Borders: #E5E7EB

Error: #DC2626

Use Inter or a similar modern sans-serif font.

### Login Page

Design a premium banking login experience.

Desktop layout:
- Two-column composition.
- Left side: SecureBank branding, welcoming heading, short description, and subtle abstract financial illustration or CSS artwork.
- Right side: Clean login form.
- Username or email field.
- Password field.
- Show/hide password.
- Login button.
- Clear validation messages.
- Demo account information in a discreet development-only section.

On mobile, stack the content vertically.

Use a clean white interface with blue accents.

### Banking Dashboard

Create a realistic but minimal dashboard containing:

- Top navigation.
- SecureBank logo.
- Welcome message.
- Simulated account balance.
- Recent activity.
- View balance button.
- Transaction history button.
- Simulated transfer request button.
- Logout button.

All action buttons must send real backend requests.

Do not implement real payments, payment gateways, or external banking APIs.

If the backend blocks the user, display a custom access-restricted page.

## PROTOCOLGUARD ADMIN DESIGN

Theme: Dark, predominantly black.

Primary background: #09090B

Sidebar: #111114

Card background: #18181B

Borders: #27272A

Primary text: #FAFAFA

Secondary text: #A1A1AA

Accent: #3B82F6

Success: #22C55E

Warning: #F59E0B

Danger: #EF4444

Use color sparingly.

The interface should resemble a modern, professional security operations platform.

### Layout

Create a fixed or collapsible sidebar with:

- Overview
- Live Monitoring
- Users
- Suspicious IPs
- Security Alerts
- FSM Visualizer
- ML Analytics
- Detector Comparison
- Simulation Lab
- Settings

The top bar should include:
- Current page title.
- Live connection status.
- Admin profile.
- Logout.

Use consistent card components, clean data tables, subtle hover states, responsive layouts, and readable charts.

Prioritize usability and visual hierarchy.

---

# 5. AUTHENTICATION AND MULTI-USER SUPPORT

Create 10 demo banking accounts.

Each account must have:
- Unique ID.
- Username.
- Securely hashed password.
- Simulated balance.
- Account status.
- Risk score.
- Created timestamp.

Implement proper authentication with secure sessions or appropriately configured tokens.

Never store plaintext passwords.

The backend must identify the authenticated user from a verified session, not from a user ID supplied by the frontend.

Support multiple simultaneous users and independent session histories.

Implement separate admin authentication and role-based authorization.

Regular banking users must never access administrative APIs.

---

# 6. SECURITY EVENT COLLECTION

Every relevant banking action must create a security event.

Events include:

- LOGIN_ATTEMPT
- LOGIN_SUCCESS
- LOGIN_FAILED
- VIEW_BALANCE
- VIEW_HISTORY
- TRANSFER_REQUEST
- LOGOUT
- UNAUTHORIZED_REQUEST
- RATE_LIMIT_TRIGGERED
- ACCESS_BLOCKED

Each event should record:

- Event ID
- User ID, if known
- Session ID, if available
- IP address
- Event type
- Timestamp
- Request endpoint
- Request outcome
- Relevant protocol/session state
- Detection metadata

Never log passwords, session tokens, or other secrets.

Obtain client IP addresses from trusted server connection information. Only trust forwarded IP headers when the reverse proxy is explicitly configured as trusted.

Persist events in the database.

The event processing pipeline must handle concurrent requests safely.

---

# 7. FINITE-STATE MACHINE ENGINE

This is the core Theory of Computation component.

Implement a deterministic finite-state machine representing banking application-session behavior.

Formally define:

M = (Q, Σ, δ, q0, F)

Where:
- Q is the set of states.
- Σ is the event alphabet.
- δ is the transition function.
- q0 is the initial state.
- F is the set of accepting states.

Suggested states:

- LOGGED_OUT
- AUTHENTICATING
- AUTHENTICATED
- VIEWING_ACCOUNT
- TRANSFER_PENDING
- BLOCKED

Define valid transitions explicitly.

Examples:

LOGGED_OUT + LOGIN_ATTEMPT → AUTHENTICATING

AUTHENTICATING + LOGIN_SUCCESS → AUTHENTICATED

AUTHENTICATING + LOGIN_FAILED → LOGGED_OUT

AUTHENTICATED + VIEW_BALANCE → VIEWING_ACCOUNT

VIEWING_ACCOUNT + RETURN → AUTHENTICATED

AUTHENTICATED + TRANSFER_REQUEST → TRANSFER_PENDING

TRANSFER_PENDING + CANCEL_TRANSFER → AUTHENTICATED

AUTHENTICATED + LOGOUT → LOGGED_OUT

Define all required transitions, including repeated valid actions, and handle unspecified transitions consistently.

Separate authentication enforcement from the analytical FSM.

The FSM must not be the only authorization mechanism.

For every sequence, record:
- Initial state.
- Events.
- Transitions.
- Invalid transitions.
- Final state.
- Acceptance result.
- Violation explanations.

Document the distinction between valid prefixes, complete accepted sessions, and suspicious sequences.

The FSM should be independently testable.

---

# 8. MACHINE LEARNING ENGINE

Implement two models.

## Model A — Random Forest

Train a supervised classifier using labeled synthetic banking activity sequences.

## Model B — Isolation Forest

Train an anomaly detection model primarily on normal banking activity.

Create a reproducible synthetic dataset generator.

Generate approximately 10,000 sessions initially, including:

- Normal banking activity.
- Failed-login bursts.
- Unauthorized access attempts.
- High-frequency requests.
- Abnormal transfer-request patterns.
- Unusual event sequences.
- Previously unseen scenario variants.

Use realistic variation in timestamps, sequence lengths, event frequencies, and behavior patterns.

Avoid generating labels solely from FSM violation outcomes.

Extract features such as:

- Event count.
- Login failure count.
- Request frequency.
- Invalid transition count.
- Transfer attempt count.
- Session duration.
- Average inter-event interval.
- Event-type frequencies.
- Transition frequencies.
- Distinct endpoint count.

Use consistent preprocessing between training and inference.

Prevent training/test leakage by splitting at the session level and grouping related synthetic scenarios where appropriate.

Evaluate:
- Accuracy.
- Precision.
- Recall.
- F1-score.
- False-positive rate.
- Confusion matrix.
- Inference time.
- Generalization to held-out scenarios.

Persist trained models and preprocessing artifacts.

Provide scripts for reproducible training and evaluation.

Do not invent model accuracy or performance results.

---

# 9. HYBRID THREAT SCORING

Create a hybrid detector combining:

- FSM violations.
- Random Forest predictions.
- Isolation Forest anomaly evidence.
- Behavioral indicators.

Generate an individual user risk index from 0 to 100.

Begin with a transparent scoring approach, but make the weights configurable.

Normalize ML outputs appropriately. Do not treat raw Isolation Forest scores as probabilities.

Do not claim that a risk score of 70 means a 70% probability of malicious behavior.

Document how evidence contributes to the final score.

Track score changes over time and preserve the reasons for each change.

Implement risk-score decay or a documented reset policy so historical low-risk activity does not produce indefinite score accumulation.

Keep user risk and IP-level risk separate.

---

# 10. AUTOMATIC BLOCKING

Implement the following initial policy:

- Risk score 0–29: Low.
- Risk score 30–60: Monitoring.
- Risk score above 60: Automatically block the user account.

The threshold must be configurable from admin settings.

When an account is blocked:

1. Persist a block record.
2. Record the reason and evidence.
3. Revoke active sessions.
4. Deny subsequent protected API requests.
5. Generate a security alert.
6. Notify the admin dashboard in real time.
7. Display a custom HTTP 403 access-restricted page to the user.

Blocking must be enforced on the backend.

The user must not bypass restrictions by refreshing the page or calling APIs directly.

## IP Blocking

Maintain a persistent suspicious-IP database.

Store:
- IP address.
- First detected timestamp.
- Last detected timestamp.
- Associated events.
- IP risk evidence.
- Block status.
- Block reason.
- Admin action history.

Do not automatically block an entire IP merely because one associated account exceeds the user-risk threshold.

Multiple legitimate users may share the same public IP.

Allow the admin to manually block and unblock IP addresses.

Support temporary IP restrictions for repeated abusive unauthenticated requests.

When an IP is blocked, reject requests at the security gateway, except for any explicitly permitted recovery or health-check endpoints.

Provide a safe development recovery mechanism to prevent accidental administrator lockout.

---

# 11. ADMIN UNBLOCK FUNCTIONALITY

The administrator must be able to:

- View blocked accounts.
- View blocked IP addresses.
- Inspect blocking reasons.
- See the associated event history.
- Manually unblock an account.
- Manually unblock an IP.
- Add an administrative note.
- Review previous block/unblock actions.

Every admin action must be recorded in an audit log.

Unblocking an account must not automatically unblock an IP, and unblocking an IP must not automatically unblock an account.

Use confirmation dialogs for destructive or security-sensitive actions.

---

# 12. ADMIN DASHBOARD FEATURES

## Overview

Display:
- Total registered users.
- Active sessions.
- Requests analyzed.
- Suspicious users.
- Blocked accounts.
- Blocked IPs.
- Alerts in the last 24 hours.
- Threat distribution chart.
- Recent incidents.

## Live Monitoring

Display real-time events with:
- Timestamp.
- User.
- IP address.
- Action.
- Threat score.
- Detection status.

Use WebSockets with reconnection handling.

## Users

Display a searchable table of users.

Allow the admin to open a user detail page showing:
- Current risk score.
- Account status.
- Associated IPs.
- Event timeline.
- FSM violations.
- ML results.
- Block history.

## Suspicious IPs

Display:
- IP address.
- Associated accounts.
- Suspicious event count.
- Last detected activity.
- Block status.
- Manual block/unblock controls.

## Security Alerts

Display alerts with severity, reason, evidence, timestamp, and resolution status.

## FSM Visualizer

Use React Flow to render the state machine.

Highlight:
- Current state.
- Valid transitions.
- Invalid transitions.
- Triggering event.
- Transition history.

Allow the admin to replay a recorded event sequence.

## ML Analytics

Display:
- Model metrics.
- Anomaly score distribution.
- Confusion matrices.
- Feature importance where supported.
- Prediction history.

## Detector Comparison

Compare:
- FSM-only detector.
- Random Forest detector.
- Isolation Forest detector.
- Hybrid detector.

Use the same labeled evaluation dataset.

Display precision, recall, F1-score, false-positive rate, and processing time.

## Simulation Lab

Provide controlled scenarios:
- Normal banking session.
- Repeated login failures.
- Unauthorized balance access.
- Rapid request bursts.
- Abnormal transfer requests.
- Mixed suspicious behavior.

Allow simultaneous simulation of multiple demo users.

The simulator must only operate on local demo accounts and isolated test endpoints.

Do not build tools that attack external websites.

Clearly distinguish simulated events from actual banking-user events.

---

# 13. DATABASE DESIGN

Create normalized SQLAlchemy models for:

- users
- admin_users
- sessions
- security_events
- risk_scores
- suspicious_ips
- blocked_entities
- security_alerts
- admin_audit_logs
- detection_results
- simulation_runs

Use proper primary keys, foreign keys, indexes, and timestamps.

Store historical detection evidence instead of overwriting it.

Implement database migrations using Alembic if practical.

Ensure concurrent event processing does not corrupt risk scores or block records.

---

# 14. API DESIGN

Create clean REST APIs.

Examples:

Banking:
- POST /api/auth/login
- POST /api/auth/logout
- GET /api/bank/balance
- GET /api/bank/history
- POST /api/bank/transfer-request

Admin:
- GET /api/admin/overview
- GET /api/admin/users
- GET /api/admin/users/{id}
- GET /api/admin/events
- GET /api/admin/alerts
- GET /api/admin/suspicious-ips
- POST /api/admin/users/{id}/block
- POST /api/admin/users/{id}/unblock
- POST /api/admin/ips/block
- POST /api/admin/ips/unblock
- GET /api/admin/fsm
- GET /api/admin/ml/metrics
- GET /api/admin/detectors/comparison

Simulation:
- POST /api/simulation/run

WebSocket:
- /ws/admin/events

All admin endpoints must require verified administrator authorization.

Use appropriate validation, rate limiting, CORS configuration, and error handling.

---

# 15. SECURITY REQUIREMENTS

This is a security-focused project, so the application itself must follow reasonable security practices.

Implement:
- Secure password hashing.
- Session expiration and revocation.
- Backend authorization checks.
- Input validation.
- Parameterized database operations.
- Rate limiting.
- Safe error messages.
- Secure cookie configuration where applicable.
- CSRF protection if cookie-based authentication is used.
- Audit logging.
- Restricted simulation endpoints.
- Environment-based secrets.
- No plaintext credentials in Git.
- No secrets in security event logs.

Use dummy financial data only.

Do not connect to real bank accounts or payment systems.

---

# 16. TESTING REQUIREMENTS

Create tests for:

- Successful login.
- Failed login.
- Multiple simultaneous users.
- Independent user risk scores.
- Valid FSM transitions.
- Invalid FSM transitions.
- ML inference.
- Hybrid risk calculation.
- Automatic blocking above 60.
- Backend denial after blocking.
- Session revocation.
- Admin account unblock.
- Admin IP unblock.
- Persistent block records.
- Shared-IP users remaining independent.
- WebSocket updates.
- Unauthorized admin API access.

Test the complete workflow from a banking action to an admin alert.

Do not claim tests pass unless they were actually executed.

---

# 17. GIT AND GITHUB WORKFLOW — MANDATORY

After every completed feature:

1. Implement the feature.
2. Run relevant tests and checks.
3. Fix errors.
4. Review changed files.
5. Update documentation if needed.
6. Create a meaningful Git commit.
7. Push the commit to the configured GitHub repository when authorized and available.
8. Report the commit hash and feature summary.

Examples:

- feat: initialize ProtocolGuard AI monorepo
- feat: implement SecureBank login interface
- feat: add banking dashboard and event tracking
- feat: implement multi-user authentication
- feat: add finite-state detection engine
- feat: generate synthetic training dataset
- feat: train Random Forest and Isolation Forest
- feat: implement hybrid risk scoring
- feat: add automatic account blocking
- feat: implement suspicious IP tracking
- feat: add admin unblock controls
- feat: build live security dashboard
- feat: add interactive FSM visualizer
- feat: implement detector comparison
- feat: add multi-user simulation lab
- test: add end-to-end security workflow tests
- docs: finalize setup and project explanation

IMPORTANT:

Before starting, inspect the current Git repository, branch, remotes, and working tree.

If the folder is not connected to GitHub, ask me for the repository URL.

Do not create a different GitHub repository without permission.

Do not overwrite unrelated work.

Do not force-push.

Do not commit secrets, environment files, local databases, or sensitive generated data.

Do not make destructive Git changes without approval.

If pushing requires authentication or permission, stop and ask me.

If a test fails, report the failure and fix it before declaring the feature complete.

Keep each commit focused on one feature or logically related change.

---

# 18. DOCUMENTATION AND LEARNING

I am a Computer Science student building this project for Theory of Computation evaluation.

I need to understand the complete system, not merely run generated code.

Create documentation explaining:

1. Overall architecture.
2. Why we use finite-state machines.
3. Formal DFA definition.
4. State-transition table.
5. Valid and invalid sequences.
6. How events are generated.
7. How the synthetic dataset is created.
8. What features are extracted.
9. How Random Forest works.
10. How Isolation Forest works.
11. How the hybrid detector works.
12. How threat scores are calculated.
13. How automatic blocking works.
14. How IP blocking differs from account blocking.
15. How the database is structured.
16. How the two frontends communicate with the backend.
17. How to run the project locally.
18. How to demonstrate the project.
19. How to interpret evaluation metrics.
20. Common viva questions and answers.

Explain major implementation decisions in simple language.

Create a README with setup commands, environment variables, architecture overview, and screenshots or screenshot instructions.

---

# 19. IMPLEMENTATION ORDER

Build incrementally in this order.

Phase 1:
- Inspect Git repository.
- Initialize project structure.
- Configure backend and both React apps.
- Create shared design foundations.

Phase 2:
- Implement SecureBank login page.
- Implement banking dashboard.
- Create demo users.
- Add authentication.

Phase 3:
- Implement event logging.
- Build banking-session FSM.
- Add FSM tests.

Phase 4:
- Generate synthetic dataset.
- Implement feature extraction.
- Train Random Forest.
- Train Isolation Forest.
- Evaluate models.

Phase 5:
- Implement hybrid risk scoring.
- Add persistent security alerts.
- Implement automatic account blocking.
- Implement suspicious-IP tracking.
- Implement admin unblock controls.

Phase 6:
- Build dark admin dashboard.
- Add real-time monitoring.
- Add user and IP management.
- Build FSM visualization.
- Add ML analytics and detector comparison.

Phase 7:
- Add controlled attack simulation.
- Test multi-user scenarios.
- Perform end-to-end testing.
- Polish responsive UI.
- Finalize documentation.

Commit each completed feature separately.

---

# 20. DEFINITION OF DONE

The project is complete only when:

- SecureBank login works.
- Banking dashboard actions generate backend events.
- Multiple users can operate simultaneously.
- Each user has an independent risk score.
- FSM detects invalid transitions.
- Trained ML models produce predictions.
- Hybrid detection calculates risk scores.
- Users exceeding the configured threshold are blocked.
- Blocked users cannot access protected banking APIs.
- Suspicious IP records persist.
- Admin can block and unblock accounts and IPs.
- Admin dashboard updates in real time.
- FSM transitions can be visualized.
- Detector comparison shows actual evaluation results.
- Controlled simulations work.
- Automated tests pass.
- Both websites run locally.
- GitHub contains feature-by-feature commits.
- Documentation explains the complete project.

---

# 21. STARTING INSTRUCTIONS

First inspect the existing folder and Git configuration.

Then:

1. Summarize the proposed architecture.
2. Identify any important implementation assumptions.
3. Check whether a GitHub remote is configured.
4. Present the first feature you will implement.
5. Begin implementation.

Do not ask unnecessary questions when a safe technical default is available.

Do not implement the entire project in one enormous unreviewable change.

Work feature by feature.

After each feature, provide:

- Feature completed.
- Files created or modified.
- Tests executed.
- Commit message.
- Commit hash.
- GitHub push status.
- Simple explanation of what the feature does.
- Next planned feature.

**Your objective is to deliver a polished, functional, academically defensible intrusion-detection platform—not just a visually attractive frontend.**