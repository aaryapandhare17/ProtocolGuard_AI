import json
import pytest
pytest.importorskip('numpy')
pytest.importorskip('sklearn')
pytest.importorskip('pandas')
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import Settings
from app.main import create_app
from app.ml.features import from_security_events
from app.models.entities import DetectionResult, SecurityEvent
from app.seed import seed
from test_auth import signin
from test_ml_training import trained


def test_real_saved_models_load_and_score_persisted_events(trained,tmp_path):
    _, artifacts, _ = trained
    instance = create_app(Settings(database_url=f'sqlite:///{tmp_path}/bank.db',ml_model_directory=str(artifacts)))
    with TestClient(instance) as client:
        seed(instance.state.session_factory,'bank-test-password','admin-test-password')
        assert instance.state.ml_status == 'ready'
        signin(client)
        client.get('/api/bank/balance')
        client.get('/api/bank/history')
        with instance.state.session_factory() as db:
            events = db.scalars(select(SecurityEvent).order_by(SecurityEvent.id)).all()
            result = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            evidence = json.loads(result.evidence)
            direct = instance.state.detector.predict(from_security_events(events))
            assert evidence['ml']['predictions'][0]['prediction'] == direct
            assert evidence['contributions']['random_forest'] == pytest.approx(35*direct['random_forest']['score'])
            assert evidence['contributions']['isolation_forest'] == pytest.approx(10*direct['isolation_forest']['anomaly_evidence'])
