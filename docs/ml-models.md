# Random Forest and Isolation Forest

## Run training and evaluation

Activate the backend virtual environment, then run from the repository root:

```sh
python -m pip install -e "backend[dev,ml]"
python -m app.ml.train --dataset ml/datasets/bank-v1 --output ml/artifacts/bank-v1 --seed 42
python -m app.ml.evaluate --dataset ml/datasets/bank-v1 --artifacts ml/artifacts/bank-v1 --output ml/evaluation/bank-v1.json
```

Generate the dataset first if needed; see [dataset documentation](ml-dataset.md).
Each command refuses to overwrite existing artifacts/reports: use a new output path.
The recorded run used Python 3.12.14 and the exact versions in `ml/requirements-training.txt`.
For that runtime, install those versions with `python -m pip install -r ml/requirements-training.txt`
before reproducing the run. Other compatible environments can train their own artifacts.

Training writes `detectors.joblib`, `artifact-manifest.json`, and `evaluation.json`.
Generated datasets, models, and evaluation outputs remain ignored by Git. The measured
report from the executed 10,000-session run is preserved in [ml-evaluation.json](ml-evaluation.json).
Reevaluation loads saved models and uses their frozen thresholds; it never fits or tunes.

## What the models do

A **Random Forest** trains many decision trees on labeled observations. Each tree learns
splits such as whether an event frequency is high or whether a transition is invalid.
Combining trees reduces dependence on a single tree. Here it uses 160 trees, balanced
class weights, and a minimum leaf size of two. The output score is an uncalibrated class
estimate from those trees; it is not a verified probability that a user is malicious.

An **Isolation Forest** learns how ordinary observations look. Random partitions isolate
unusual points more quickly. Here its 160 trees train **only on normal training observations**;
suspicious training observations are excluded. `-score_samples` makes higher raw scores
mean more anomalous. These raw scores are not probabilities, and the built-in contamination
threshold is not used for our final classification.

Both models use the same 90-feature extractor as runtime inference, in its fixed order.
Tree models do not require scaling, so there is no fitted scaler to leak test information.
The artifact persists both estimators, the exact feature/DFA schema, package version,
thresholds, normal-score reference distribution, dataset hashes, and random seed.

## Sessions in progress and labels

Training adds observations at 25%, 50%, and 75% of each sequence, deduplicating repeated
prefix lengths. Every observation keeps its source session ID, recipe group, and partition.
The complete observation always keeps the dataset label. Benign prefixes keep label zero.
For suspicious scenarios, prefix labels change only after their defined synthetic attack onset:

| Synthetic scenario | First observable suspicious prefix |
| --- | --- |
| failed_login_burst | Three failed logins |
| rapid_requests | Ten balance/history actions in the generated rapid pattern |
| transfer_burst / heldout_paced_transfer | Four transfer requests |
| unauthorized_access | First unauthorized request |
| invalid_sequence | The intentionally misplaced RETURN event |

These are ground-truth conventions for the generator, not detection rules applied by the
trained models. They avoid labeling a shared, innocent-looking login prefix malicious simply
because its future session contains an attack. Prefix metrics still contain correlated
observations, so complete-session results are reported separately.

For the recorded run, 6,498 training sessions produced 25,835 observations. Isolation Forest
used only the 15,442 normal training observations. Metadata, source labels, future events,
and partition names are excluded from feature inputs.

## Threshold selection

For each model, the training command evaluates 61 score quantiles and an all-negative
fallback **on validation observations only**. It maximizes validation F1 among thresholds
with validation false-positive rate at most 5%; ties prefer lower FPR, then recall and a
higher threshold. No test or held-out observation is used for fitting or threshold selection.

The recorded thresholds are 0.0125 for Random Forest and 0.5838056624059736 for Isolation
Forest. A low RF threshold reflects the chosen validation objective, not a conventional
50% probability cutoff. The 5% constraint applies to the combined validation observations;
it does not guarantee a 5% rate on every subset or on unseen data.

## Measured results

These numbers come from the executed run, not estimates. Complete test sessions include
1,346 examples; held-out sessions include 776. Positive class means suspicious.

| Model / complete partition | Accuracy | Precision | Recall | F1 | False-positive rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Random Forest / test | 99.93% | 99.83% | 100.00% | 99.91% | 0.13% |
| Isolation Forest / test | 77.86% | 78.35% | 66.32% | 71.83% | 13.58% |
| Random Forest / held-out | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% |
| Isolation Forest / held-out | 99.74% | 99.48% | 100.00% | 99.74% | 0.51% |

The held-out families are not uniformly harder: slow normal browsing and paced transfer
patterns can remain separable by the learned features. Perfect synthetic results do not
establish real-world accuracy. Isolation Forest's high complete-test false-positive rate
and missed suspicious sessions are preserved; test results were not used to retune it.

Test-prefix F1 is 96.88% for Random Forest and 59.77% for Isolation Forest. The full report
includes validation, complete/prefix/combined observations, per-scenario results, confusion
matrices, feature importance, training times, dependency versions, and measured latency.
Confusion matrices use true rows and predicted columns in `[normal, suspicious]` order.
Some per-scenario rows contain only benign examples; positive-class F1 is then zero by
definition in this report, so inspect their confusion matrix and false-positive rate.

Single-vector median inference times in the recorded environment were approximately 5.01 ms
for RF and 5.32 ms for IF, each measured over 40 warmed-up observations. These timings exclude
feature extraction, database access, and networking, and vary across runs and computers.

**Accuracy** measures the fraction of all correct predictions. **Precision** asks how many
flagged observations were suspicious. **Recall** asks how many suspicious observations were
caught. **F1** balances precision and recall. **False-positive rate** counts benign observations
incorrectly flagged, divided by all benign observations. Reported sample counts matter:
a high score on a small or simple synthetic family should not be generalized to real users.

## Runtime inference

```python
from app.ml.inference import DetectorBundle
from app.ml.features import from_security_events

detector = DetectorBundle.load("ml/artifacts/bank-v1")
# rows must be ordered security events from the observation being analyzed
result = detector.predict(from_security_events(rows), complete=False)
```

The result contains scores, frozen thresholds, decisions, event count, and a provisional flag.
Set `complete=True` only when the caller knows its observation is complete. Empty observations
are rejected. The load path is a trusted local artifact directory, never an uploaded model;
joblib files can execute code. Checksums detect corruption, not hostile replacement by an
attacker able to change both a model and its manifest. Feature/schema or scikit-learn-version
mismatches are rejected; retrain in the new environment instead of silently loading them.

Isolation output also includes its empirical percentile relative to normal **validation** scores.
`anomaly_evidence = clip((percentile - 0.95) / 0.05, 0, 1)` scales just the upper reference tail
into a bounded evidence value. It does not turn an anomaly score into a probability of attack.

The inference service now contributes to [hybrid scoring](hybrid-risk.md) through the
banking event pipeline. [Account enforcement](account-blocking.md) now acts on the combined
risk score; a model prediction alone is not a block decision. There is no
prediction upload endpoint; artifacts are generated and loaded from trusted local storage.

Measured models and operational prediction history are now visible in the admin dashboard.
The [four-detector comparison](ml-analytics.md) adds FSM-only and frozen hybrid policy
evaluation on the same observations without retraining or retuning.
