import pytest

pytest.importorskip("sklearn")
from fastapi.testclient import TestClient
from app.ml.dataset import build_dataset
from app.ml.train import train_models
from app.ml.validate_live import replay, TIMING_CASES
from app.main import create_app
from app.core.config import Settings
from test_blocking import admin_login


@pytest.fixture(scope="module")
def release_models(tmp_path_factory):
    root = tmp_path_factory.mktemp("login-release")
    build_dataset(root / "dataset", count=10000, seed=42)
    train_models(root / "dataset", root / "artifacts", seed=42)
    return root / "artifacts"


@pytest.mark.parametrize("latency,gap", TIMING_CASES)
def test_real_models_block_paced_failures_by_15_without_manual_enforcement(
    release_models, latency, gap
):
    result = replay(release_models, latency, gap)
    assert result["blocked"] and result["block_source"] == "automatic"
    assert result["protected_status"] == 403
    assert len(result["attempts"]) <= 15 and result["attempts"][-1]["seconds"] <= 60
    assert result["unrelated_account_unchanged"]


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_normal_retries_and_success_keep_valid_access(release_models, count):
    result = replay(release_models, 2, 4, failed_logins=count, normal_retry=True)
    assert not result["blocked"] and result["protected_status"] == 200
    assert result["unrelated_account_unchanged"]


def test_failures_outside_window_do_not_become_a_fixed_attempt_lockout(release_models):
    result = replay(release_models, 1, 25)
    assert not result["blocked"] and len(result["attempts"]) == 15


def test_projected_model_metadata_remains_available_to_admin(release_models, tmp_path):
    from app.seed import seed

    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/analytics.db",
            ml_model_directory=str(release_models),
        )
    )
    with TestClient(app) as admin:
        seed(app.state.session_factory, "bank-test-password", "admin-test-password")
        admin_login(admin)
        response = admin.get("/api/admin/ml/metrics")
        assert response.status_code == 200
        assert response.json()["status"] == "available", response.json()
        assert (
            response.json()["report"]["dataset"]["generator_version"]
            == "bank-synthetic-v2"
        )
