# Viva questions and design decisions

**What makes this a Theory of Computation project?**
A deterministic finite-state machine formalizes the legal ordering of banking
session events. Its states, alphabet and transition function are explicit and
versioned. The visualizer and replay expose actual persisted applications of that
function. See [the formal FSM reference](fsm.md) for the exact state/event table.

**What does determinism mean here?**
For a particular state and event the engine has one defined result. The same
versioned input produces the same transition. Timing and ML scores can vary while
that transition rule remains deterministic.

**Why combine FSM and ML?**
Protocol rules explain invalid sequencing. Learned features can identify unusual
activity that still follows valid transitions. Combining evidence supplies more
signals but does not guarantee better performance on every cohort; the comparison
page reports the measured outcomes of each method.

**How do Random Forest and Isolation Forest differ?**
Random Forest learns labeled normal/suspicious examples. Isolation Forest learns
normal-only training observations and measures deviation from that baseline.
The runtime uses their frozen artifacts, thresholds and shared numeric features.

**How was leakage reduced?**
Dataset splits group observations by original session. Prefixes from one session
remain in its partition. Thresholds are chosen on validation data; evaluation uses
separate test and unseen held-out scenario families. Isolation Forest is fitted
only on normal training examples. Read [ML models](ml-models.md) for the details.

**Does 99% synthetic accuracy prove banking fraud detection?**
No. Accuracy depends on synthetic scenario construction and class balance. Report
precision, recall, false positives and confusion matrices for the selected cohort.
Real-world validation would require representative, appropriately governed data.

**How is risk calculated?**
A configured weighted combination of FSM, RF, IF and behavioral evidence produces
an assessment. Historical risk decays over time. Each stored assessment retains its
component evidence, policy and account association. See [hybrid risk](hybrid-risk.md).

**What if the models cannot load?**
The system labels the model state and missing evidence explicitly. It does not
invent RF/IF scores. Rule and behavioral evidence continue, with potentially reduced
detection. Artifact integrity and feature/version checks reject incompatible bundles.

**Can bypassing the UI bypass a block?**
No. Backend authorization checks sessions and account/IP restrictions. Blocking
revokes sessions. Protected banking calls are denied even if the browser retained
its old cookie. The UI translates that denial into the restricted-access screen.

**Why are users and IPs separate?**
Several people can share an address, and one person can change addresses. Account
risk belongs to the verified identity. IP abuse/restrictions describe observed
network activity and have separate evidence, expiry and recovery.

**How are concurrent updates handled?**
SQLite write transactions begin immediately to serialize state-changing work and
avoid lost updates. The event, risk and enforcement changes commit together. The
lab runs against separate temporary databases and releases the source transaction
while its bounded actors execute.

**Why not trust X-Forwarded-For everywhere?**
A client can supply that header. Only a verified hosting proxy should be trusted
to translate it into the ASGI client address. Incorrect trust permits fabricated
addresses; no trust behind a proxy can group visitors under that proxy's address.

**How is the lab safe and reproducible?**
It has a fixed scenario catalog, demo-user allowlist, bounded actors/requests and
in-process ASGI transport. It cannot accept an external target. Only its saved
snapshots/audits enter the live database. A seed reproduces the plan, while actual
runtime scheduling and model decisions can vary.

**What would change for a larger deployment?**
Use managed migrations, a multi-instance database, shared stream/worker coordination,
durable background jobs, operational backups/retention and monitoring. Validate
trusted proxy topology, secure transport and real-world detector calibration.
The current implementation is a single-instance academic demonstration.
