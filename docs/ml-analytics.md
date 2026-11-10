# ML analytics and detector comparison

## Generate and serve measured results

The administrator dashboard now includes **ML analytics** and **Detector comparison**.
Sign in with the provisioned admin credentials. These pages read saved evaluation files
and persisted operational assessments; they never train models through an HTTP request.

From the repository root, with the backend environment activated:

```sh
python -m pip install -e "backend[dev,ml]"
python -m app.ml.dataset --sessions 10000 --seed 42 --output ml/datasets/bank-v1
python -m app.ml.train --dataset ml/datasets/bank-v1 --output ml/artifacts/bank-v1
python -m app.ml.compare --dataset ml/datasets/bank-v1 --artifacts ml/artifacts/bank-v1 --output ml/evaluation/comparison-v1.json
```

Skip generation/training when those outputs already exist. Commands refuse to overwrite;
choose new paths for repeat runs. The API reads the training report from
`ML_MODEL_DIRECTORY/evaluation.json` and comparison from `ML_COMPARISON_REPORT`, whose
default is `ml/evaluation/comparison-v1.json`. Restart the backend after changing model
artifacts so runtime inference and saved metadata agree.

Reproducible source is committed; generated dataset/model files remain ignored. The executed
10,000-session comparison is preserved in [detector-comparison.json](detector-comparison.json),
and the original RF/IF training report remains in [ml-evaluation.json](ml-evaluation.json).

## Analytics page

The saved synthetic evaluation section provides:

- Validation, test, and held-out partition selection.
- Complete-session, prefix, and combined observation views.
- Accuracy, precision, recall, F1 and false-positive rate for both models.
- Confusion matrices with explicit true-row/predicted-column axes and sample counts.
- Frozen decision thresholds, recorded model-only timing, and top-ten RF feature importances.

Feature importance is impurity-based and does not establish causality. The shared feature
schema includes DFA violation and transition statistics; RF is not a detector trained on
entirely independent inputs from the FSM.

The separate operational section reads the latest 100 persisted detection assessments.
A session and failed-login window can yield separate predictions from one assessment.
The table shows actual model scores, empirical normal-reference percentiles, context,
provisional/complete state, account, timestamp, and historical hybrid risk. The raw IF score
histogram bins only available finite observations. These are recent correlated records,
not a population sample, labeled test set, or new accuracy measurement.

RF runtime scores, raw IF scores and normal-reference percentiles are not calibrated
probabilities of malicious behavior. Missing live prediction fields display unavailable
markers rather than invented zero values. Saved evaluation availability and runtime model
coverage are displayed separately.

## Fair comparison protocol

The comparison command uses the same validated dataset, partitions, prefix labeling,
feature extraction, and observations for all four detectors. It performs no fit or threshold
selection. RF/IF decisions match their original frozen evaluation exactly.

- **FSM only:** suspicious when the observed sequence is rejected or ends BLOCKED.
- **Random Forest:** frozen class-score threshold from validation.
- **Isolation Forest:** frozen raw-anomaly threshold from validation.
- **Hybrid:** the shared weighted assessment formula using RF score, normalized IF tail
  evidence, FSM evidence and in-session rolling behavioral evidence; suspicious above 60.

Hybrid evaluation is a **single-session instantaneous assessment** with the default declared
policy. It does not include retained previous scores, cross-session failed-login aggregation,
account/IP enforcement, or administrator risk resets. Those are account-pipeline behaviors,
not independent labels available for this controlled snapshot comparison. The report records
its exact policy and threshold. A dashboard warning appears if live policy settings differ.
The library function `compare_detectors` can accept an explicitly chosen policy/threshold;
changing it must be documented and must not use test results to choose settings.

Complete-session results use one observation per source session. Prefixes remain in their
source groups/partitions, but are correlated; their metrics must be interpreted separately.
Held-out scenario families are unseen in fitting, not guaranteed to be harder than known families.

## Executed complete-test results

All rows below use the same 1,346 synthetic complete test sessions:

| Detector | Accuracy | Precision | Recall | F1 | False-positive rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| FSM only | 71.77% | 100.00% | 33.68% | 50.39% | 0.00% |
| Random Forest | 99.93% | 99.83% | 100.00% | 99.91% | 0.13% |
| Isolation Forest | 77.86% | 78.35% | 66.32% | 71.83% | 13.58% |
| Hybrid | 95.47% | 100.00% | 89.35% | 94.38% | 0.00% |

The FSM misses protocol-valid abuse such as request bursts. The hybrid eliminates the RF's
one false positive in this cohort but misses 61 suspicious sessions, compared with zero
missed by RF. This is a transparent policy tradeoff, not evidence that hybrid is always best.
No threshold was retuned against these test results. Synthetic accuracy does not establish
real-world banking performance.

Processing benchmarks use the same first 40 complete test sessions, starting from raw events.
Required feature/context extraction is included; model loading, database access and network
latency are excluded. Recorded median times were approximately 0.009 ms (FSM), 5.775 ms (RF),
5.808 ms (IF), and 12.061 ms (hybrid). Hardware and scheduling affect these values. The timing
column always describes this fixed test-session benchmark, even when viewing another cohort.

## API validation and availability

Read-only routes require verified administrator authorization:

- `GET /api/admin/ml/metrics`: saved RF/IF evaluation, source and runtime availability.
- `GET /api/admin/ml/predictions?limit=100`: actual predictions in bounded recent assessments;
  limit is 1–200, with the scanned count and sampling scope included.
- `GET /api/admin/detectors/comparison`: verified comparison and live-policy-match indicator.

The backend checks feature/schema versions, model metadata/thresholds, dataset fingerprints,
artifact hashes, finite/bounded metrics, confusion-matrix counts and metric arithmetic. All
four comparison rows must have identical cohort counts. Missing or incompatible reports return
an explicit unavailable state; the API does not substitute committed example statistics.
The UI renders that state without charts or metric rows, while operational history remains
available independently. Paths come from trusted server configuration, not user-supplied URLs.

## Verification

Tests assert no model fitting during comparison, RF/IF parity with original evaluation,
cohort equality, measured timing fields, overwrite protection, report binding, policy mismatch,
admin authorization, missing/corrupt files, private/bounded live history, confusion-matrix
consistency, and histogram endpoint/empty/constant cases. Browser checks cover measured values,
partition/scope changes, live history, four-detector charts, unavailable-state behavior,
policy mismatch and restoration, and mobile layout without root horizontal overflow.
