"""Measured binary classification metrics; positive class is suspicious (1)."""
import time
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


def classification_metrics(labels, predictions):
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average="binary", zero_division=0)
    return {"samples": len(labels), "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "false_positive_rate": float(fp/(tn+fp)) if tn+fp else 0.0,
        "confusion_matrix": matrix.tolist(), "confusion_matrix_axes": "rows=true, columns=predicted; order=[normal,suspicious]"}


def select_threshold(labels, scores, maximum_fpr=0.05):
    # Only validation inputs belong here. Include an all-negative fallback.
    candidates = np.unique(np.r_[np.quantile(scores, np.linspace(0, 1, 61)), np.nextafter(np.max(scores), np.inf)])
    eligible = []
    for threshold in candidates:
        metrics = classification_metrics(labels, scores >= threshold)
        if metrics["false_positive_rate"] <= maximum_fpr:
            eligible.append((metrics["f1"], -metrics["false_positive_rate"], metrics["recall"], float(threshold)))
    if not eligible:
        raise ValueError("No threshold satisfies validation FPR policy")
    return max(eligible)[-1]


def latency(predict, features, count=40):
    sample = features[:count]
    predict(sample[:1])  # Warm up; exclude it from timing.
    durations = []
    for row in sample:
        start = time.perf_counter_ns()
        predict(row.reshape(1, -1))
        durations.append((time.perf_counter_ns()-start)/1_000_000)
    return {"median_ms": float(np.median(durations)), "p95_ms": float(np.percentile(durations, 95)),
        "observations": len(durations), "scope": "single precomputed feature vector; excludes feature extraction, network and database"}


def evaluate_partitions(score, threshold, partitions):
    from app.ml.features import FEATURE_NAMES
    measured = {}
    for split in ("validation", "test", "held_out"):
        frame = partitions[split]
        labels = frame.label.to_numpy(dtype=int)
        predictions = score(frame[list(FEATURE_NAMES)].to_numpy(dtype=float)) >= threshold
        measured[split] = {"all_observations": classification_metrics(labels, predictions)}
        for kind in ("complete", "prefix"):
            mask = frame.observation.to_numpy() == kind
            measured[split][kind] = classification_metrics(labels[mask], predictions[mask])
        measured[split]["by_scenario_complete"] = {
            scenario: classification_metrics(labels[mask], predictions[mask])
            for scenario in sorted(set(frame.scenario))
            if (mask := ((frame.scenario.to_numpy() == scenario) & (frame.observation.to_numpy() == "complete"))).any()
        }
    return measured
