# Login timing coverage: model release v2

## Goal and unchanged policy

The release targets automatic blocking **by 15 completed failed logins within a
rolling 60 seconds**, using the existing weighted risk policy and strict `score > 60`
comparison. It does not implement a fixed-attempt lockout. Weights remain
FSM 30%, RF 35%, IF 10%, behavior 25%; the window remains 60 seconds and the risk
half-life remains ten minutes. Existing Neon accounts and history require no migration.

The reported live assessment contained only three recent failures. Its new score
was 17.47, while retained risk had decayed to 40.75. That correctly stayed below 60.
The old synthetic data also represented login processing as roughly millisecond
pairs; local ultra-fast tests therefore overstated hosted coverage.

## Training changes

`bank-synthetic-v2` adds paced failures and held-out jittered failure sequences,
with varied server-processing latency applied to benign authentication and attacks.
Normal retry controls remain separate from suspicious sequences. Recipe groups and
session prefixes stay in their original train/validation/test partitions; held-out
families do not enter fitting. Isolation Forest is fitted only on training
observations labeled normal.

RF retains all 90 shared features. IF now uses a saved scikit-learn pipeline that
projects those inputs onto the 12 base activity features. This avoids diluting
count/timing novelty across redundant transition fractions. The projection is
fixed before fitting and persisted with the estimator; it does not add a runtime
count rule or alter the scoring weights. Both models still accept the same
versioned 90-feature input contract.

The first expanded-data candidate with the old IF representation missed the target
near 59.98. It was not selected for deployment. The release pipeline passed the
checks below. This was iterative synthetic development, not an independent real-bank
validation study. RF/IF classifier flags and actual hybrid enforcement are reported
separately; standalone IF has substantial held-out false positives and must not be
presented as independently reliable enforcement.

## Executed results

The 10,000-session release uses seed 42 and 160 trees per estimator. On the same
v2 complete test plus held-out cohort:

| Scenario | Old model positive decisions | Release positive decisions |
| --- | --- | --- |
| Paced failed logins | 0 / 142 | 142 / 142 |
| Unseen jittered failed logins | 0 / 312 | 312 / 312 |
| Benign complete observations | 0 / 1,392 false blocks | 0 / 1,392 false blocks |
| Paced transfers | 0 / 314 | 0 / 314 |

Paced transfers remain a known coverage gap; this release does not fix every
attack family. Combined test/held-out hybrid recall improved from 28.72% to 74.21%
on that identical expanded cohort. These are synthetic instantaneous snapshot
comparisons, not network or live account-enforcement measurements.

The separate actual-handler acceptance gate uses an isolated ASGI application,
real saved models, a controlled UTC clock and the ordinary authentication/risk/
enforcement code. All six timing profiles blocked automatically by attempt 15
within 60 seconds (observed first blocks: attempts 6–8). The previously valid
session received HTTP 403. Twelve controls covering zero to three benign retries
and a successful login stayed unblocked. Fifteen failures spaced outside the
window did not become a fixed-attempt lockout. Unrelated accounts stayed unchanged.

Reports:

- [RF/IF evaluation](ml-evaluation-v2.json)
- [Four-detector comparison](detector-comparison-v2.json)
- [Same-cohort baseline/candidate audit](login-model-comparison-v2.json)
- [Actual-handler acceptance traces](login-coverage-v2.json)

## Deployment and verification

The backend Docker builds generate `bank-v2` artifacts and matching reports, then
run `python -m app.ml.validate_live` before producing a deployable image. A failed
gate fails the build. The old model artifacts are not silently overwritten locally.
No passwords or customer records are used in training or build-time checks.

After GitHub checks pass, Render's configured automatic deployment can build the
new backend. If it does not start, use **Manual Deploy → Deploy latest commit**.
No manual Vercel deployment is required for the model update. Keep Neon credentials,
CORS and account provisioning settings unchanged. If you explicitly overrode
`ML_MODEL_DIRECTORY`/`ML_COMPARISON_REPORT` on Render, update them to
`/app/ml/artifacts/bank-v2` and `/app/ml/evaluation/comparison-v2.json`.

After Render shows the release commit as Live:

1. Sign into the production admin URL and verify ML is Ready.
2. While signed in, open `/api/admin/ml/metrics` on the Vercel origin. The response's
   `report.dataset.generator_version` should be `bank-synthetic-v2`.
3. Use a dedicated active demo account with a valid banking session open, then
   perform the bounded failed-login demonstration from another browser context.
4. Watch the account's risk and automatic alert evidence. Stop when blocked, and
   confirm the original session is denied.
5. Unblock/reset risk afterward and sign in afresh.

A deliberately wrong password can still return HTTP 401 after blocking. Check the
admin account state and the previously valid session's HTTP 403 to prove enforcement.

The target requires failures to complete inside the rolling minute. Fifteen attempts
spread over several minutes are a different case. Free-host sleep, database latency
and human pacing can affect the completed-request rate. Controlled-clock acceptance
is evidence of pipeline behavior, not a guarantee of every live-network outcome.
