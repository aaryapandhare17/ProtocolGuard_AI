"""Verify dataset provenance and make partition-preserving prefix observations."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from app.ml.dataset import METADATA_COLUMNS
from app.ml.features import ActivityEvent, FEATURE_NAMES, extract_features, feature_schema
from app.ml.synthetic import GENERATOR_VERSION, HELDOUT_SCENARIOS


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prefix_label(scenario, source_label, events):
    """Known synthetic attack onset, not a rule used by the trained detector."""
    if source_label == 0:
        return 0
    kinds = [event.event_type for event in events]
    if scenario in {"failed_login_burst", "failed_login_paced", "heldout_jittered_login_failures"}:
        return int(kinds.count("LOGIN_FAILED") >= 3)
    if scenario == "rapid_requests":
        return int(sum(kind in {"VIEW_BALANCE", "VIEW_HISTORY"} for kind in kinds) >= 10)
    if scenario in {"transfer_burst", "heldout_paced_transfer"}:
        return int(kinds.count("TRANSFER_REQUEST") >= 4)
    if scenario == "unauthorized_access":
        return int("UNAUTHORIZED_REQUEST" in kinds)
    if scenario == "invalid_sequence":
        return int("RETURN" in kinds)
    raise ValueError("Unknown suspicious scenario for prefix labeling")


def load_observations(directory, include_prefixes=True):
    directory = Path(directory)
    manifest = json.loads((directory/"manifest.json").read_text())
    if manifest.get("feature_schema") != feature_schema() or manifest.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("Dataset feature or generator version mismatch")
    for filename in ("features.csv", "sessions.jsonl"):
        if sha256(directory/filename) != manifest["files"][filename]["sha256"]:
            raise ValueError(f"Dataset checksum mismatch: {filename}")
    frame = pd.read_csv(directory/"features.csv")
    if list(frame.columns) != list(METADATA_COLUMNS)+list(FEATURE_NAMES):
        raise ValueError("Dataset column order does not match the feature contract")
    if len(frame) != manifest["session_count"] or not frame.session_id.is_unique:
        raise ValueError("Dataset session count mismatch or duplicate sessions")
    if set(frame.split) != {"train", "validation", "test", "held_out"} or not frame.label.isin([0, 1]).all():
        raise ValueError("Dataset needs all four partitions and binary labels")
    if not np.isfinite(frame[list(FEATURE_NAMES)].to_numpy(dtype=float)).all():
        raise ValueError("Dataset contains nonfinite feature values")
    if frame.groupby("group_id").split.nunique().max() != 1:
        raise ValueError("Related groups cross dataset partitions")
    for row in frame.itertuples(index=False):
        if manifest["group_assignments"].get(row.group_id) != row.split:
            raise ValueError("Group assignment does not match manifest")
        if (row.scenario in HELDOUT_SCENARIOS) != (row.split == "held_out"):
            raise ValueError("Held-out scenario leaked into another partition")
    indexed = frame.set_index("session_id", drop=False)
    rows, seen = [], set()
    with (directory/"sessions.jsonl").open() as raw:
        for line in raw:
            session = json.loads(line)
            session_id = session["session_id"]
            if session_id not in indexed.index or session_id in seen:
                raise ValueError("Raw session IDs do not match feature rows")
            seen.add(session_id)
            source = indexed.loc[session_id]
            if any(session[name] != source[name] for name in METADATA_COLUMNS):
                raise ValueError("Raw session metadata disagrees with CSV")
            events = tuple(ActivityEvent(**event) for event in session["events"])
            full = extract_features(events)
            if not np.allclose(list(full.values()), source[list(FEATURE_NAMES)].to_numpy(dtype=float), rtol=1e-12, atol=1e-12):
                raise ValueError("Raw session features disagree with CSV")
            rows.append({**source.to_dict(), "observation": "complete", "observed_events": len(events)})
            if include_prefixes:
                lengths = sorted({max(1, int(len(events)*fraction)) for fraction in (0.25, 0.5, 0.75)})
                for length in lengths:
                    if length >= len(events):
                        continue
                    prefix = events[:length]
                    rows.append({**{name: session[name] for name in METADATA_COLUMNS},
                        "label": prefix_label(session["scenario"], session["label"], prefix),
                        **extract_features(prefix), "observation": "prefix", "observed_events": length})
    if seen != set(indexed.index):
        raise ValueError("Some feature rows have no raw session")
    return pd.DataFrame(rows), manifest
