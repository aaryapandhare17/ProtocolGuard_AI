"""Compare frozen detectors on identical grouped synthetic observations, without fitting."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace
import numpy as np
from app.fsm.engine import INITIAL_STATE, step
from app.ml.features import ActivityEvent, FEATURE_NAMES, feature_vector, feature_schema
from app.ml.inference import DetectorBundle
from app.ml.metrics import classification_metrics
from app.ml.observations import load_observations, sha256
from app.security.risk import RiskPolicy, behavioral_evidence, combine

COMPARISON_VERSION = "bank-comparison-v1"


def fsm_evidence(events):
    state, last = INITIAL_STATE, None
    for event in events:
        last = step(state, event.event_type)
        state = last.state_after
    return float(bool(last and not last.valid) or state == "BLOCKED")


def snapshot_context(events, policy):
    fsm = fsm_evidence(events)
    cutoff = events[-1].timestamp - policy.window_seconds
    recent = [
        SimpleNamespace(
            event_type=event.event_type,
            created_at=datetime.fromtimestamp(event.timestamp, timezone.utc).replace(
                tzinfo=None
            ),
        )
        for event in events
        if event.timestamp >= cutoff
    ][-policy.max_events :]
    return fsm, behavioral_evidence(recent)["value"]


def summarize(frame, predictions):
    labels = frame.label.to_numpy(dtype=int)
    results = {"all_observations": classification_metrics(labels, predictions)}
    for kind in ("complete", "prefix"):
        mask = frame.observation.to_numpy() == kind
        results[kind] = classification_metrics(labels[mask], predictions[mask])
    return results


def benchmark(detector, policy, events_list, threshold):
    bundle = detector.bundle

    def rf(events):
        vector = np.asarray([feature_vector(events)])
        return (
            bundle["random_forest"].predict_proba(vector)[0, 1]
            >= bundle["random_forest_threshold"]
        )

    def isolation(events):
        vector = np.asarray([feature_vector(events)])
        return (
            -bundle["isolation_forest"].score_samples(vector)[0]
            >= bundle["isolation_forest_threshold"]
        )

    def hybrid(events):
        prediction = detector.predict(events)
        fsm, behavior = snapshot_context(events, policy)
        return (
            combine(
                policy,
                fsm=fsm,
                rf=prediction["random_forest"]["score"],
                isolation=prediction["isolation_forest"]["anomaly_evidence"],
                behavior=behavior,
            )["score"]
            > threshold
        )

    functions = {
        "fsm_only": lambda events: bool(fsm_evidence(events)),
        "random_forest": rf,
        "isolation_forest": isolation,
        "hybrid": hybrid,
    }
    measured = {}
    for name, predict in functions.items():
        predict(events_list[0])
        durations = []
        for events in events_list:
            started = time.perf_counter_ns()
            predict(events)
            durations.append((time.perf_counter_ns() - started) / 1_000_000)
        measured[name] = {
            "median_ms": float(np.median(durations)),
            "p95_ms": float(np.percentile(durations, 95)),
            "samples": len(durations),
            "scope": "raw complete-session events to decision, including required feature/context extraction; excludes database and network",
        }
    return measured


def compare_detectors(dataset, artifacts, output, policy=None, threshold=60):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Comparison report already exists; choose a new path")
    if not np.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("Hybrid threshold must be between zero and 100")
    policy = policy or RiskPolicy()
    detector = DetectorBundle.load(artifacts)
    observations, manifest = load_observations(dataset)
    if detector.bundle["dataset_checksums"] != manifest["files"]:
        raise ValueError("Dataset provenance differs from trained artifact")
    groups = observations.groupby("session_id").groups
    contexts = np.zeros((len(observations), 2))
    benchmark_events = []
    with (Path(dataset) / "sessions.jsonl").open() as raw:
        for line in raw:
            session = json.loads(line)
            events = tuple(ActivityEvent(**row) for row in session["events"])
            for index in groups[session["session_id"]]:
                length = int(observations.at[index, "observed_events"])
                contexts[index] = snapshot_context(events[:length], policy)
            if session["split"] == "test" and len(benchmark_events) < 40:
                benchmark_events.append(events)
    if not benchmark_events:
        raise ValueError("No complete test sessions to benchmark")
    results = {
        name: {"metrics": {}}
        for name in ("fsm_only", "random_forest", "isolation_forest", "hybrid")
    }
    for split in ("validation", "test", "held_out"):
        frame = observations[observations.split == split]
        x = frame[list(FEATURE_NAMES)].to_numpy(dtype=float)
        rf = detector.bundle["random_forest"].predict_proba(x)[:, 1]
        raw = -detector.bundle["isolation_forest"].score_samples(x)
        percentile = np.searchsorted(detector.reference, raw, side="right") / len(
            detector.reference
        )
        isolation = np.clip((percentile - 0.95) / 0.05, 0, 1)
        scores = np.array(
            [
                combine(
                    policy,
                    fsm=contexts[index, 0],
                    rf=float(rf[position]),
                    isolation=float(isolation[position]),
                    behavior=contexts[index, 1],
                )["score"]
                for position, index in enumerate(frame.index)
            ]
        )
        decisions = {
            "fsm_only": contexts[frame.index, 0].astype(bool),
            "random_forest": rf >= detector.bundle["random_forest_threshold"],
            "isolation_forest": raw >= detector.bundle["isolation_forest_threshold"],
            "hybrid": scores > threshold,
        }
        for name, predictions in decisions.items():
            results[name]["metrics"][split] = summarize(frame, predictions)
    timing = benchmark(detector, policy, benchmark_events, threshold)
    for name in results:
        results[name]["latency"] = timing[name]
    report = {
        "version": COMPARISON_VERSION,
        "feature_schema": feature_schema(),
        "model_sha256": sha256(Path(artifacts) / "detectors.joblib"),
        "dataset": {
            "files": manifest["files"],
            "seed": manifest["seed"],
            "sessions": manifest["session_count"],
            "split_sessions": manifest["split_counts"],
        },
        "observation_counts": observations.split.value_counts().to_dict(),
        "policy": policy.describe(),
        "hybrid_threshold": threshold,
        "thresholds": {
            "random_forest": detector.bundle["random_forest_threshold"],
            "isolation_forest": detector.bundle["isolation_forest_threshold"],
        },
        "models": results,
        "tuning": "No fitting or threshold selection. Frozen model thresholds and declared hybrid policy.",
        "hybrid_scope": "Single-session instantaneous assessment; rolling in-session behavior only; no prior-score retention, cross-session login window, account/IP enforcement, or admin resets.",
        "limitations": [
            "Synthetic evaluation does not establish real-world accuracy.",
            "Prefix observations from the same session are correlated; complete-session counts are reported separately.",
            "The live account pipeline includes cross-session evidence and decay; this controlled detector comparison measures single-session snapshots.",
            "Timing uses the same first 40 complete test sessions for all detectors and varies with hardware.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("ml/datasets/bank-v1"))
    parser.add_argument("--artifacts", type=Path, default=Path("ml/artifacts/bank-v1"))
    parser.add_argument(
        "--output", type=Path, default=Path("ml/evaluation/comparison-v1.json")
    )
    args = parser.parse_args()
    try:
        report = compare_detectors(args.dataset, args.artifacts, args.output)
    except (ValueError, FileExistsError) as error:
        parser.exit(2, str(error) + "\n")
    print(
        json.dumps(
            {
                name: model["metrics"]["test"]["complete"]
                for name, model in report["models"].items()
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
