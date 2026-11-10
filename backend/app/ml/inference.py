"""Load locally trained, trusted artifacts and predict with the shared extractor."""
import json
from pathlib import Path
import joblib
import numpy as np
import sklearn
from app.ml.features import FEATURE_NAMES, feature_schema, feature_vector
from app.ml.observations import sha256

ARTIFACT_VERSION = "bank-detectors-v1"


class DetectorBundle:
    def __init__(self, bundle):
        if bundle.get("artifact_version") != ARTIFACT_VERSION or bundle.get("feature_schema") != feature_schema():
            raise ValueError("Incompatible model artifact or feature contract")
        if bundle.get("sklearn_version") != sklearn.__version__:
            raise ValueError("scikit-learn version mismatch; retrain using this environment")
        if any(bundle[name].n_features_in_ != len(FEATURE_NAMES) for name in ("random_forest", "isolation_forest")):
            raise ValueError("Model feature width mismatch")
        if list(bundle["random_forest"].classes_) != [0, 1]:
            raise ValueError("Random Forest must contain both classes")
        reference = np.asarray(bundle["isolation_reference"], dtype=float)
        if reference.ndim != 1 or not len(reference) or not np.isfinite(reference).all():
            raise ValueError("Invalid Isolation Forest reference distribution")
        if not all(np.isfinite(bundle[name]) for name in ("random_forest_threshold", "isolation_forest_threshold")):
            raise ValueError("Invalid model thresholds")
        self.bundle = bundle
        self.reference = np.sort(reference)

    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        manifest = json.loads((directory/"artifact-manifest.json").read_text())
        if manifest.get("artifact_version") != ARTIFACT_VERSION or sha256(directory/"detectors.joblib") != manifest.get("sha256"):
            raise ValueError("Model artifact checksum or version mismatch")
        # joblib can execute code: only load artifacts trained in a trusted local workspace.
        instance=cls(joblib.load(directory/"detectors.joblib"))
        instance.artifact_sha256=manifest["sha256"]
        return instance

    def predict(self, events, initial_state="LOGGED_OUT", *, complete=False):
        events = tuple(events)
        if not events:
            raise ValueError("At least one event is needed for inference")
        features = np.asarray([feature_vector(events, initial_state)], dtype=float)
        rf = float(self.bundle["random_forest"].predict_proba(features)[0, 1])
        raw = float(-self.bundle["isolation_forest"].score_samples(features)[0])
        percentile = float(np.searchsorted(self.reference, raw, side="right")/len(self.reference))
        return {"artifact_version": ARTIFACT_VERSION, "feature_version": self.bundle["feature_schema"]["version"],
            "event_count": len(events), "provisional": not complete,
            "random_forest": {"score": rf, "threshold": self.bundle["random_forest_threshold"],
                "suspicious": bool(rf >= self.bundle["random_forest_threshold"])},
            "isolation_forest": {"raw_anomaly_score": raw, "threshold": self.bundle["isolation_forest_threshold"],
                "suspicious": bool(raw >= self.bundle["isolation_forest_threshold"]),
                "normal_reference_percentile": percentile,
                "anomaly_evidence": float(np.clip((percentile-0.95)/0.05, 0, 1))},
            "score_note": "Scores and normal-reference percentiles are evidence, not calibrated probabilities of malicious behavior."}
