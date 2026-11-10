# Synthetic sessions and the ML feature contract

## Scope

This feature generates labeled activity, assigns partitions, and extracts features.
It does not train models or report model accuracy. The generator makes no HTTP requests
and uses no real accounts, IP addresses, payments, or customer data.

Run from the repository root with the backend environment activated:

```sh
python -m app.ml.dataset --sessions 10000 --seed 42 --output ml/datasets/bank-v1
```

The output directory contains:

- `sessions.jsonl`: one complete synthetic session per line, including ordered events,
  epoch timestamps, API paths, scenario, recipe group, binary label, and partition.
- `features.csv`: one row per session, with metadata followed by the 90 ordered numeric features.
- `manifest.json`: generator/feature/DFA versions, seed, partitions, class counts, recipe
  assignments, feature order, and SHA-256 hashes and sizes of both data files.

The command refuses to overwrite existing dataset files. Choose a new output directory
for another run. Generated files remain ignored by Git; the source code reproduces them.
File contents are deterministic for the same seed and code version. The manifest omits
wall-clock generation times and absolute output paths so independent runs can match byte for byte.
Only Python's standard library is needed for this stage.

## Scenarios and labels

| Scenario | Label | Behavior |
| --- | --- | --- |
| normal_browsing | 0 | Short sessions with balance/history views |
| normal_transfer | 0 | One to three simulated transfer requests |
| normal_busy | 0 | Longer legitimate sessions with frequent browsing |
| normal_retry | 0 | One or two failed login attempts followed by normal use |
| failed_login_burst | 1 | Six to 25 rapid failed-login cycles |
| unauthorized_access | 1 | Repeated requests without authentication |
| rapid_requests | 1 | Authenticated, high-frequency balance/history requests |
| transfer_burst | 1 | Many rapidly repeated simulated transfer requests |
| invalid_sequence | 1 | Actions in an undefined protocol order |
| heldout_slow_normal | 0 | Unseen normal sessions with long pauses |
| heldout_paced_transfer | 1 | Unseen suspicious transfer pattern at a slower pace |

Labels represent the intended synthetic scenario, assigned independently of DFA results.
Failed-login, rapid-request, and transfer-burst sequences can have zero DFA violations while
being labeled suspicious. Normal retry and busy sessions add benign variation.
These are assumptions for a college demonstration, not labels derived from real incidents.

Each family has 20 parameter recipes. Sampling changes sequence lengths, activity choices,
inter-event intervals, and the number of transfer/login attempts. Paired authentication and
transfer-recording events get short delays because they are produced within one request.

## Partitions and leakage controls

For each ordinary scenario, a seed-specific shuffle assigns its 20 recipes to 14 training,
three validation, and three test groups. Every repetition of a scenario/recipe stays in its
assigned partition; an entire session occupies exactly one row and one partition. The two
held-out families appear exclusively in `held_out`, including both benign and suspicious examples.

Because the scenario sampling is weighted, the final row counts are approximate, not exact
70/15/15 proportions. For the executed seed-42, 10,000-session run:

| Partition | Sessions |
| --- | ---: |
| train | 6,498 |
| validation | 1,380 |
| test | 1,346 |
| held_out | 776 |

Future training must use `train` to fit preprocessing/models, `validation` to choose settings,
`test` for final evaluation within known families, and `held_out` for unseen-family evaluation.
Related prefix/subsequence augmentations must inherit their source session's group and split.
Do not concatenate datasets from different seeds without rechecking group assignments.

`session_id`, `scenario`, `group_id`, `split`, and `label` are metadata columns, never model
inputs. Future training must select only the exact `feature_schema.feature_names` list from
the manifest. No username, absolute start time, scenario name, or label is a numeric feature.
Shared recipe grouping reduces leakage between closely related synthetic examples; it does
not make this synthetic dataset representative of real-world banking traffic.

## Shared feature extraction

`backend/app/ml/features.py` supplies `ActivityEvent`, `extract_features`, `feature_vector`,
and `from_security_events`. Dataset export and future inference use the same code and feature
ordering. `from_security_events` converts database timestamps to epoch seconds, interpreting
naive timestamps as UTC. Callers must pass chronologically ordered events from one session.
An optional initial DFA state supports historical partial traces; new sessions start LOGGED_OUT.

The `bank-features-v1` schema contains 90 features:

| Features | Count | Meaning |
| --- | ---: | --- |
| Base statistics | 12 | Event/login-failure/transfer counts; invalid-transition count and fraction; duration; rate; mean/min interval; short-interval fraction; endpoint diversity; unknown-event count |
| Event fractions | 14 | Count of each event in the DFA alphabet divided by total event count |
| State-transition fractions | 64 | Count for every ordered pair of the eight DFA states divided by total event count |

Duration is the last timestamp minus the first. Mean/min intervals use adjacent timestamps.
A short interval is less than 0.25 seconds. `request_frequency` is an **event-rate proxy**:
`max(event_count - 1, 0) / max(duration_seconds, 1.0)`. Multiple security events can come from
one HTTP request, so this is not an exact HTTP request count. The one-second denominator floor
keeps zero-duration and extremely short observations finite.

Empty sessions produce a zero vector. Single-event sessions have zero duration and rate.
Equal timestamps are allowed; decreasing, nonnumeric, or nonfinite timestamps are rejected.
Unknown event names increment `unknown_event_count` and enter the DFA's rejecting sink.
Unknown events are included in normalization denominators; known-event fractions can sum below one.
Absolute start times do not affect feature values.

## Validation and limitations

Tests check hand-calculated feature values, fixed order, empty/zero-duration observations,
unknown events, timestamp validation, database/synthetic parity, deterministic seeds, recipe
partitioning, independent labels, metadata exclusion, export hashes, and overwrite protection.
A full generation run is also checked for group overlap and recomputed feature consistency.

This first dataset uses complete session observations. Live predictions may need prefixes,
so the training feature must add/evaluate prefix observations without crossing group partitions.
Synthetic scenarios are simplified and intentionally separable in places; even excellent metrics
on them would not establish production readiness or a probability of malicious behavior.

Next: train and persist Random Forest and Isolation Forest artifacts, with actual measured
validation/test/held-out metrics and consistent preprocessing.
