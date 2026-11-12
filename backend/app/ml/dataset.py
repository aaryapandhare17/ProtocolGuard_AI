"""Export reproducible JSONL sessions, feature CSV and an auditable manifest."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from itertools import chain
from pathlib import Path
from app.ml.features import FEATURE_NAMES, extract_features, feature_schema
from app.ml.synthetic import GENERATOR_VERSION, HELDOUT_SCENARIOS, generate_sessions

METADATA_COLUMNS = ("session_id", "scenario", "group_id", "split", "label")


def build_dataset(output: Path, count: int = 10000, seed: int = 42) -> dict:
    # Validate before opening outputs. Exclusive file creation avoids silent overwrite.
    sessions = generate_sessions(count, seed)
    first = next(sessions)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    paths = [output/name for name in ("sessions.jsonl", "features.csv", "manifest.json")]
    if any(path.exists() for path in paths):
        raise FileExistsError("Dataset files already exist; choose a new output directory")
    split_counts, scenario_counts, labels, group_splits = Counter(), Counter(), defaultdict(Counter), {}
    with paths[0].open("x", encoding="utf-8", newline="\n") as raw, paths[1].open("x", encoding="utf-8", newline="") as features:
        writer = csv.DictWriter(features, fieldnames=METADATA_COLUMNS+FEATURE_NAMES, lineterminator="\n")
        writer.writeheader()
        for session in chain((first,), sessions):
            if session.group_id in group_splits and group_splits[session.group_id] != session.split:
                raise ValueError("Related scenario group crosses dataset partitions")
            group_splits[session.group_id] = session.split
            raw.write(json.dumps(session.to_dict(), sort_keys=True, separators=(",", ":"))+"\n")
            writer.writerow({**{name: getattr(session, name) for name in METADATA_COLUMNS}, **extract_features(session.events)})
            split_counts[session.split] += 1
            scenario_counts[session.scenario] += 1
            labels[session.split][str(session.label)] += 1
    manifest = {
        "generator_version": GENERATOR_VERSION, "seed": seed, "session_count": count,
        "feature_schema": feature_schema(), "metadata_columns": list(METADATA_COLUMNS),
        "split_counts": dict(split_counts), "scenario_counts": dict(scenario_counts),
        "labels_by_split": {name: dict(values) for name, values in labels.items()},
        "group_assignments": group_splits, "held_out_scenarios": sorted(HELDOUT_SCENARIOS),
        "files": {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in paths[:2]},
        "limitations": ["Synthetic behavior does not establish real-world detection performance.",
            "Labels reflect scenario intent, not just DFA violations.",
            "Sessions are complete observations; prefix augmentation must retain their group partitions.",
            "Metadata columns are excluded from model inputs; use only feature_schema.feature_names.",
            "Use validation for tuning, test for final in-family evaluation, held_out for unseen scenarios."],
    }
    with paths[2].open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("ml/datasets/bank-v2"))
    args = parser.parse_args()
    try:
        manifest = build_dataset(args.output, args.sessions, args.seed)
    except (ValueError, FileExistsError) as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps({"output": str(args.output), "sessions": manifest["session_count"], "splits": manifest["split_counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
