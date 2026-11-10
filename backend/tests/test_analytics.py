import json
import pytest
from fastapi.testclient import TestClient
from app.services.analytics import validate_metrics
from test_auth import app, signin
from test_blocking import admin_login
from test_risk import ConstantDetector


def test_analytics_role_checks_and_missing_invalid_reports(app, tmp_path):
    with TestClient(app) as client:
        for path in ("/ml/metrics", "/ml/predictions", "/detectors/comparison"):
            assert client.get("/api/admin" + path).status_code == 401
        signin(client)
        assert client.get("/api/admin/ml/metrics").status_code == 401
        admin_login(client)
        app.state.settings = app.state.settings.model_copy(
            update={
                "ml_model_directory": str(tmp_path),
                "ml_comparison_report": str(tmp_path / "comparison.json"),
            }
        )
        assert client.get("/api/admin/ml/metrics").json()["status"] == "unavailable"
        assert (
            client.get("/api/admin/detectors/comparison").json()["status"]
            == "unavailable"
        )
        (tmp_path / "evaluation.json").write_text("not-json")
        assert client.get("/api/admin/ml/metrics").json()["status"] == "unavailable"
        (tmp_path / "comparison.json").write_text("{}")
        assert (
            client.get("/api/admin/detectors/comparison").json()["status"]
            == "unavailable"
        )


def test_live_prediction_history_is_bounded_persisted_and_private(app):
    with TestClient(app) as bank, TestClient(app) as admin:
        app.state.detector, app.state.ml_status = ConstantDetector(), "ready"
        signin(bank)
        bank.get("/api/bank/balance")
        bank.get("/api/bank/history")
        admin_login(admin)
        history = admin.get("/api/admin/ml/predictions?limit=1").json()
        assert history["assessments_scanned"] == 1 and len(history["predictions"]) == 1
        assert history["predictions"][0]["random_forest"]["score"] == 0.8
        assert history["predictions"][0]["username"] == "demo01"
        assert "password_hash" not in json.dumps(history)
        assert bank.cookies.get("pg_bank") not in json.dumps(history)
        assert admin.get("/api/admin/ml/predictions?limit=201").status_code == 422


def test_metric_validation_rejects_inconsistent_or_nonfinite_reports():
    metric = {
        "samples": 4,
        "confusion_matrix": [[1, 1], [1, 1]],
        "accuracy": 0.5,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "false_positive_rate": 0.5,
    }
    report = {
        "model": {
            "metrics": {
                split: {
                    scope: dict(metric)
                    for scope in ("complete", "prefix", "all_observations")
                }
                for split in ("validation", "test", "held_out")
            }
        }
    }
    validate_metrics(report, ["model"])
    report["model"]["metrics"]["test"]["complete"]["accuracy"] = 0.9
    with pytest.raises(ValueError):
        validate_metrics(report, ["model"])
    report["model"]["metrics"]["test"]["complete"]["accuracy"] = float("nan")
    with pytest.raises(ValueError):
        validate_metrics(report, ["model"])
