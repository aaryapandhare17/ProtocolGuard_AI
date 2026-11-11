# Presentation and demonstration

This is an academic banking-security simulation. All balances and transfers are dummy
data. Keep passwords, cookies and CSRF tokens out of screenshots and slides.

## Five-minute explanation

ProtocolGuard combines a formal banking protocol with learned activity patterns.
SecureBank generates backend events from authenticated actions. A deterministic
finite-state machine checks each transition. Random Forest and Isolation Forest
provide additional evidence from the same versioned feature extractor. Weighted,
decaying risk evidence can trigger server-side account blocks and revoke sessions.
Independent IP tracking catches network abuse without treating an IP as a user.
Administrators inspect evidence, recover accounts and visualize recorded transitions.

The frontend never authorizes banking access. Every protected API verifies the
persistent session, account state, IP restriction and, for writes, CSRF token.
The FSM analyzes behavior; it does not replace authentication.

## Demonstration sequence

1. Start the API and both websites following README. Provision dummy accounts and
   generate models/reports using the ML guides. Open two browser profiles: one for
   SecureBank and one for ProtocolGuard Admin.
2. Sign into SecureBank as `demo01`. View balance and activity, record one small
   simulated transfer and log out. Point out the unchanged dummy balance.
3. In Admin, open Live monitoring and Users. Show actual event records and the
   account's individual risk/evidence history. Sign in as `demo02` in another profile
   to demonstrate independent sessions and scores.
4. Open FSM visualizer. Select the recorded session and replay its transitions.
   Explain accepted transitions and why a rejected event leaves violation evidence.
5. Open ML analytics. Explain the synthetic data source, complete versus prefix
   observations, held-out families, precision/recall and confusion matrices. Show
   Detector comparison: all four methods use the same selected cohort. Read the
   measured values on screen rather than memorizing a universal accuracy claim.
6. In the local development Simulation lab, select two actors and repeated login
   failures. Confirm the isolated scope and run it. Inspect real HTTP outcomes,
   per-account risk, separate IP restrictions and alert evidence. Demonstrate the
   normal scenario as a control. Results depend on the loaded models and policy.
7. Manually block a dedicated demo account through a confirmed admin action with
   a note. Show the bank rejecting its existing session. Unblock with risk reset,
   then sign in again: recovery does not revive an old revoked session.
8. Show persistent security settings and audit logs. Reload the admin website to
   demonstrate persisted events and results. Finish with test results and the
   feature-by-feature Git history.

Production intentionally denies simulation execution. Present those scenarios
locally; the hosted service can demonstrate normal banking, monitoring and recovery.
Avoid deliberately restricting a shared demonstration IP: it can also deny the admin
browser on that address. Use the isolated lab for network-abuse demonstrations.

## Screenshot checklist

Capture the bank dashboard, admin overview, event evidence, FSM replay, ML evaluation,
four-detector comparison and isolated simulation results. Include one mobile layout.
Use the interface's actual numbers and labels. A screenshot of a control is not proof
that backend enforcement works; demonstrate the denied API/session as well.

## Known boundaries

The dataset is generated, not real bank traffic. Its measured accuracy does not
establish effectiveness on production financial fraud. Live prefix predictions are
provisional; scores are evidence, not calibrated probabilities. SQLite is suitable
for a single-instance academic deployment, with backups and a persistent disk.
Training/report generation happens explicitly, not on incoming web requests.
