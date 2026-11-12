"""Reproducible training and final evaluation for both banking activity models."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import time
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from app.ml.features import BASE_FEATURES, FEATURE_NAMES, feature_schema
from app.ml.inference import ARTIFACT_VERSION, DetectorBundle
from app.ml.metrics import evaluate_partitions, latency, select_threshold
from app.ml.observations import load_observations, sha256


def train_models(dataset, output, seed=42, trees=160):
    output = Path(output)
    targets = [
        output / name
        for name in ("detectors.joblib", "artifact-manifest.json", "evaluation.json")
    ]
    if any(path.exists() for path in targets):
        raise FileExistsError(
            "Model files already exist; choose a new artifact directory"
        )
    if trees < 1:
        raise ValueError("Tree count must be positive")
    observations, manifest = load_observations(dataset)
    partitions = {
        name: observations[observations.split == name]
        for name in ("train", "validation", "test", "held_out")
    }
    for name, frame in partitions.items():
        if set(frame.label) != {0, 1}:
            raise ValueError(
                f"Partition {name} requires normal and suspicious examples"
            )
    x = {
        name: frame[list(FEATURE_NAMES)].to_numpy(dtype=float)
        for name, frame in partitions.items()
    }
    y = {name: frame.label.to_numpy(dtype=int) for name, frame in partitions.items()}
    rf = RandomForestClassifier(
        n_estimators=trees,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )
    isolation = Pipeline(
        [
            (
                "activity",
                ColumnTransformer(
                    [("base", "passthrough", list(range(len(BASE_FEATURES))))]
                ),
            ),
            (
                "detector",
                IsolationForest(
                    n_estimators=trees,
                    max_samples=256,
                    contamination="auto",
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )
    started = time.perf_counter()
    rf.fit(x["train"], y["train"])
    rf_fit_seconds = time.perf_counter() - started
    started = time.perf_counter()
    isolation.fit(x["train"][y["train"] == 0])
    isolation_fit_seconds = time.perf_counter() - started
    rf_threshold = select_threshold(
        y["validation"], rf.predict_proba(x["validation"])[:, 1]
    )
    validation_anomaly = -isolation.score_samples(x["validation"])
    isolation_threshold = select_threshold(y["validation"], validation_anomaly)
    reference = np.sort(validation_anomaly[y["validation"] == 0])
    bundle = {
        "artifact_version": ARTIFACT_VERSION,
        "feature_schema": feature_schema(),
        "sklearn_version": sklearn.__version__,
        "random_forest": rf,
        "isolation_forest": isolation,
        "random_forest_threshold": rf_threshold,
        "isolation_forest_threshold": isolation_threshold,
        "isolation_reference": reference,
        "isolation_feature_names": list(BASE_FEATURES),
        "dataset_checksums": manifest["files"],
        "seed": seed,
    }
    DetectorBundle(bundle)  # Validate the in-memory contract before saving.
    models = {
        "random_forest": (
            lambda data: rf.predict_proba(data)[:, 1],
            rf_threshold,
            rf_fit_seconds,
        ),
        "isolation_forest": (
            lambda data: -isolation.score_samples(data),
            isolation_threshold,
            isolation_fit_seconds,
        ),
    }
    evaluation = {}
    for model, (score, threshold, fit_seconds) in models.items():
        measured = evaluate_partitions(score, threshold, partitions)
        evaluation[model] = {
            "threshold": threshold,
            "fit_seconds": fit_seconds,
            "latency": latency(score, x["test"]),
            "metrics": measured,
        }
    report = {
        "artifact_version": ARTIFACT_VERSION,
        "feature_schema": feature_schema(),
        "dataset": {
            "generator_version": manifest["generator_version"],
            "seed": manifest["seed"],
            "sessions": manifest["session_count"],
            "files": manifest["files"],
            "split_sessions": manifest["split_counts"],
            "held_out_scenarios": manifest["held_out_scenarios"],
        },
        "training_seed": seed,
        "trees_per_model": trees,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "observation_counts": {name: len(frame) for name, frame in partitions.items()},
        "training_labels": dict(Counter(map(str, y["train"]))),
        "isolation_training_normal_observations": int(sum(y["train"] == 0)),
        "threshold_policy": "maximize validation F1 with validation FPR <= 0.05; no test/held-out tuning",
        "preprocessing": "Shared 90-feature extractor; RF uses all features; IF projects to 12 base activity features to avoid redundant transition fractions. No scaling.",
        "isolation_feature_names": list(BASE_FEATURES),
        "prefix_policy": "25%, 50%, 75% prefixes plus complete sessions; prefix labels use known synthetic attack onset; source groups/splits retained",
        "models": evaluation,
        "random_forest_feature_importance": {
            name: float(value)
            for name, value in zip(FEATURE_NAMES, rf.feature_importances_, strict=True)
        },
        "limitations": [
            "Synthetic-only metrics do not establish real-world performance.",
            "Prefix metrics contain correlated observations; complete-session metrics use one observation per source session.",
            "Raw Isolation Forest anomaly scores and empirical normal-reference percentiles are not maliciousness probabilities.",
            "Model-only feature-vector latency excludes feature extraction, database, and network overhead.",
            "Runtime combines model evidence with configured FSM/behavior evidence; no fixed failed-attempt lockout is introduced.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, targets[0], compress=3)
    targets[1].write_text(
        json.dumps(
            {
                "artifact_version": ARTIFACT_VERSION,
                "sha256": sha256(targets[0]),
                "sklearn_version": sklearn.__version__,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    targets[2].write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("ml/datasets/bank-v2"))
    parser.add_argument("--output", type=Path, default=Path("ml/artifacts/bank-v2"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        report = train_models(args.dataset, args.output, args.seed)
    except (ValueError, FileExistsError) as error:
        parser.exit(2, f"{error}\n")
    print(
        json.dumps(
            {
                name: {
                    split: model["metrics"][split]["complete"]
                    for split in ("test", "held_out")
                }
                for name, model in report["models"].items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
