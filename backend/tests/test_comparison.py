import json
import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("pandas")
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.ml.compare import compare_detectors
from app.seed import seed
from test_ml_training import trained
from test_blocking import admin_login, action


def test_same_cohort_frozen_predictions_and_verified_reporting(
    trained, tmp_path, monkeypatch
):
    from sklearn.ensemble import RandomForestClassifier, IsolationForest

    def no_fit(*args, **kwargs):
        raise AssertionError("Comparison must not fit or tune models")

    monkeypatch.setattr(RandomForestClassifier, "fit", no_fit)
    monkeypatch.setattr(IsolationForest, "fit", no_fit)
    dataset, artifacts, original = trained
    output = tmp_path / "comparison.json"
    report = compare_detectors(dataset, artifacts, output)
    for split in ("validation", "test", "held_out"):
        for scope in ("complete", "prefix", "all_observations"):
            counts = {
                model["metrics"][split][scope]["samples"]
                for model in report["models"].values()
            }
            assert len(counts) == 1
            for name in ("random_forest", "isolation_forest"):
                assert (
                    report["models"][name]["metrics"][split][scope]
                    == original["models"][name]["metrics"][split][scope]
                )
    assert all(
        model["latency"]["median_ms"] >= 0 for model in report["models"].values()
    )
    with pytest.raises(FileExistsError):
        compare_detectors(dataset, artifacts, output)
    instance = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/api.db",
            ml_model_directory=str(artifacts),
            ml_comparison_report=str(output),
        )
    )
    with TestClient(instance) as admin:
        seed(
            instance.state.session_factory, "bank-test-password", "admin-test-password"
        )
        headers = admin_login(admin)
        assert admin.get("/api/admin/ml/metrics").json()["status"] == "available"
        response = admin.get("/api/admin/detectors/comparison").json()
        assert response["status"] == "available" and response["runtime_policy_match"]
        action(
            admin,
            "/api/admin/settings/security",
            headers,
            block_threshold=61,
            auto_block_enabled=True,
        )
        assert (
            admin.get("/api/admin/detectors/comparison").json()["runtime_policy_match"]
            is False
        )
        corrupt = json.loads(output.read_text())
        corrupt["model_sha256"] = "mismatched"
        output.write_text(json.dumps(corrupt))
        assert (
            admin.get("/api/admin/detectors/comparison").json()["status"]
            == "unavailable"
        )
