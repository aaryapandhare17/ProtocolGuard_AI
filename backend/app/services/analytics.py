"""Validated saved evaluation projections; no model fitting in HTTP requests."""

import json
import math
from pathlib import Path
from app.ml.features import feature_schema


def validate_metrics(models, names):
    for name in names:
        for split in ("validation", "test", "held_out"):
            for scope in ("complete", "prefix", "all_observations"):
                metric = models[name]["metrics"][split][scope]
                for field in (
                    "accuracy",
                    "precision",
                    "recall",
                    "f1",
                    "false_positive_rate",
                ):
                    value = metric[field]
                    if (
                        type(value) not in (int, float)
                        or not math.isfinite(value)
                        or not 0 <= value <= 1
                    ):
                        raise ValueError("Invalid classification metric")
                matrix = metric["confusion_matrix"]
                if (
                    len(matrix) != 2
                    or any(len(row) != 2 for row in matrix)
                    or any(
                        type(value) is not int or value < 0
                        for row in matrix
                        for value in row
                    )
                ):
                    raise ValueError("Invalid confusion matrix")
                if (
                    type(metric["samples"]) is not int
                    or sum(map(sum, matrix)) != metric["samples"]
                ):
                    raise ValueError("Confusion matrix does not match sample count")
                tn, fp = matrix[0]
                fn, tp = matrix[1]
                precision = tp / (tp + fp) if tp + fp else 0
                recall = tp / (tp + fn) if tp + fn else 0
                expected = {
                    "accuracy": (tn + tp) / metric["samples"]
                    if metric["samples"]
                    else 0,
                    "precision": precision,
                    "recall": recall,
                    "f1": 2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0,
                    "false_positive_rate": fp / (tn + fp) if tn + fp else 0,
                }
                if any(
                    not math.isclose(metric[name], value, abs_tol=1e-8)
                    for name, value in expected.items()
                ):
                    raise ValueError("Metrics disagree with confusion matrix")


def saved_evaluation(app):
    directory = Path(app.state.settings.ml_model_directory)
    try:
        report = json.loads((directory / "evaluation.json").read_text())
        artifact = json.loads((directory / "artifact-manifest.json").read_text())
        if (
            report["artifact_version"] != artifact["artifact_version"]
            or report["feature_schema"] != feature_schema()
        ):
            raise ValueError("Incompatible evaluation contract")
        validate_metrics(report["models"], ("random_forest", "isolation_forest"))
        detector = app.state.detector
        if detector:
            bundle = detector.bundle
            if getattr(detector, "artifact_sha256", None) != artifact["sha256"]:
                raise ValueError("Saved model manifest differs from loaded model")
            if any(
                report["trees_per_model"]
                != getattr(bundle[name], "named_steps", {})
                .get("detector", bundle[name])
                .n_estimators
                for name in ("random_forest", "isolation_forest")
            ):
                raise ValueError("Model configuration differs from saved report")
            if (
                report["dataset"]["files"] != bundle["dataset_checksums"]
                or report["training_seed"] != bundle["seed"]
                or report["versions"]["scikit_learn"] != bundle["sklearn_version"]
            ):
                raise ValueError("Evaluation does not match active model metadata")
            for name, key in (
                ("random_forest", "random_forest_threshold"),
                ("isolation_forest", "isolation_forest_threshold"),
            ):
                if report["models"][name]["threshold"] != bundle[key]:
                    raise ValueError("Evaluation thresholds differ from active models")
        return {
            "status": "available",
            "source": "saved_synthetic_evaluation",
            "model_status": app.state.ml_status,
            "runtime_model_loaded": detector is not None,
            "report": report,
            "artifact_sha256": artifact["sha256"],
        }
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "reason": "Saved model evaluation is missing. Train the models first.",
            "model_status": app.state.ml_status,
        }
    except (ValueError, KeyError, TypeError, OSError):
        return {
            "status": "unavailable",
            "reason": "Saved evaluation is invalid or does not match the active model.",
            "model_status": app.state.ml_status,
        }


def saved_comparison(app):
    try:
        report = json.loads(Path(app.state.settings.ml_comparison_report).read_text())
        if (
            report["version"] != "bank-comparison-v1"
            or report["feature_schema"] != feature_schema()
        ):
            raise ValueError("Comparison contract mismatch")
        validate_metrics(
            report["models"],
            ("fsm_only", "random_forest", "isolation_forest", "hybrid"),
        )
        for split in ("validation", "test", "held_out"):
            for scope in ("complete", "prefix", "all_observations"):
                if (
                    len(
                        {
                            report["models"][name]["metrics"][split][scope]["samples"]
                            for name in report["models"]
                        }
                    )
                    != 1
                ):
                    raise ValueError("Detector cohorts differ")
        evaluation = saved_evaluation(app)
        if (
            evaluation["status"] != "available"
            or report["model_sha256"] != evaluation["artifact_sha256"]
            or report["dataset"]["files"] != evaluation["report"]["dataset"]["files"]
        ):
            raise ValueError("Comparison provenance mismatch")
        runtime = app.state.detector
        if runtime and report["model_sha256"] != getattr(
            runtime, "artifact_sha256", None
        ):
            raise ValueError("Comparison does not match loaded artifact")
        return {
            "status": "available",
            "source": "saved_synthetic_comparison",
            "report": report,
        }
    except FileNotFoundError:
        return {
            "status": "unavailable",
            "reason": "Detector comparison is missing. Run the comparison command first.",
        }
    except (ValueError, KeyError, TypeError, OSError):
        return {
            "status": "unavailable",
            "reason": "Comparison is invalid or does not match the saved models and dataset.",
        }
