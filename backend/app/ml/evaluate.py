"""Evaluate saved detectors on their original partitions; never fit or tune models."""
import argparse
import json
from pathlib import Path
from app.ml.inference import DetectorBundle
from app.ml.metrics import evaluate_partitions
from app.ml.observations import load_observations


def evaluate_saved(dataset, artifacts):
    detector = DetectorBundle.load(artifacts)
    observations, manifest = load_observations(dataset)
    if detector.bundle["dataset_checksums"] != manifest["files"]:
        raise ValueError("Dataset provenance differs from the trained artifact")
    partitions = {name: observations[observations.split == name] for name in ("validation", "test", "held_out")}
    bundle = detector.bundle
    return {
        "random_forest": evaluate_partitions(lambda data: bundle["random_forest"].predict_proba(data)[:, 1], bundle["random_forest_threshold"], partitions),
        "isolation_forest": evaluate_partitions(lambda data: -bundle["isolation_forest"].score_samples(data), bundle["isolation_forest_threshold"], partitions),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("ml/datasets/bank-v1"))
    parser.add_argument("--artifacts", type=Path, default=Path("ml/artifacts/bank-v1"))
    parser.add_argument("--output", type=Path, default=Path("ml/evaluation/bank-v1.json"))
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise FileExistsError("Evaluation output already exists; choose a new path")
        results = evaluate_saved(args.dataset, args.artifacts)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            json.dump(results, handle, indent=2, sort_keys=True, allow_nan=False)
        print(f"Saved evaluation to {args.output}")
    except (ValueError, FileExistsError) as error:
        parser.exit(2, str(error))


if __name__ == "__main__":
    main()
