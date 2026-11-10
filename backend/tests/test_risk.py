from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.core.config import Settings
from app.database.store import now
from app.models.entities import DetectionResult, RiskScore, SecurityEvent, User
from app.security.risk import RiskPolicy, behavioral_evidence, combine, decay
from app.services.risk import current_risk, load_detector
from test_auth import app, signin


class ConstantDetector:
    def predict(self, events, **kwargs):
        return {'random_forest': {'score': .8}, 'isolation_forest': {'anomaly_evidence': .6},
                'event_count': len(events), 'provisional': not kwargs.get('complete', False)}


def test_weighted_score_and_nonaccumulation():
    policy = RiskPolicy()
    result = combine(policy, fsm=1, rf=.8, isolation=.6, behavior=.4)
    assert result['assessment_score'] == pytest.approx(74)
    assert result['contributions'] == pytest.approx({'fsm':30,'random_forest':28,'isolation_forest':6,'behavior':10})
    assert result['level'] == 'high'
    repeat = combine(policy, fsm=1, rf=.8, isolation=.6, behavior=.4, previous_score=result['score'], elapsed_seconds=1)
    assert repeat['score'] == pytest.approx(74)
    assert combine(policy, fsm=0, rf=0, isolation=0, behavior=0, previous_score=80, elapsed_seconds=600)['score'] == 40
    assert decay(100, 1200, 600) == 25
    assert decay(80, -1, 600) == 80
    assert combine(policy, fsm=1, rf=1, isolation=1, behavior=1)['score'] == pytest.approx(100)


@pytest.mark.parametrize('kwargs', [{'fsm_weight':.9}, {'rf_weight':float('nan')}, {'half_life_seconds':0}])
def test_invalid_policy(kwargs):
    with pytest.raises(ValueError):
        RiskPolicy(**kwargs)
    with pytest.raises(ValidationError):
        Settings(**{'risk_'+name:value for name,value in kwargs.items()})


def test_invalid_component_and_level_boundaries():
    policy = RiskPolicy(fsm_weight=1, rf_weight=0, if_weight=0, behavior_weight=0)
    for value, expected in [(.29,'low'), (.30,'monitoring'), (.60,'monitoring'), (.61,'high')]:
        assert combine(policy, fsm=value, rf=0, isolation=0, behavior=0)['level'] == expected
    for value in (float('nan'),float('inf'),-1,2):
        with pytest.raises(ValueError):
            combine(policy, fsm=value, rf=0, isolation=0, behavior=0)


def test_behavior_counts_logical_requests_and_failures():
    timestamp = now()
    rows = [SimpleNamespace(event_type=kind, created_at=timestamp) for _ in range(8) for kind in ('LOGIN_ATTEMPT','LOGIN_FAILED')]
    evidence = behavioral_evidence(rows)
    assert evidence['counts']['failed_logins'] == 8
    assert evidence['counts']['requests'] == 8
    assert evidence['value'] == 1
    assert behavioral_evidence([])['value'] == 0
    benign = [SimpleNamespace(event_type=kind, created_at=timestamp) for kind in ('LOGIN_ATTEMPT','LOGIN_SUCCESS','VIEW_BALANCE','VIEW_HISTORY')]
    assert behavioral_evidence(benign)['value'] == 0


def test_pipeline_persists_user_isolation_and_admin_history(app):
    with TestClient(app) as first, TestClient(app) as second:
        app.state.detector, app.state.ml_status = ConstantDetector(), 'ready'
        signin(first)
        first.get('/api/bank/balance')
        first.get('/api/bank/history')
        first.get('/api/bank/balance')
        signin(second, 'demo02')
        with app.state.session_factory() as db:
            assert db.get(User,1).risk_score == pytest.approx(34)
            assert db.get(User,2).risk_score == 0
            detections = db.scalars(select(DetectionResult)).all()
            assert len(detections) == db.scalar(select(func.count()).select_from(SecurityEvent))
            assert len(db.scalars(select(RiskScore)).all()) == len(detections)
            result = json.loads(detections[3].evidence)
            assert result['ip_risk_included'] is False
            assert result['scope'] == 'user'
            assert result['ml']['status'] == 'ready'
            assert result['reasons']
        assert first.get('/api/admin/users/1/risk').status_code == 401
        signin(first,'admin','admin-test-password',True)
        response = first.get('/api/admin/users/1/risk').json()
        assert response['stored_score'] == pytest.approx(34)
        assert response['history'][0]['score'] == pytest.approx(34)
        assert first.get('/api/admin/users/999/risk').status_code == 404
        assert first.get('/api/admin/users/1/risk?limit=201').status_code == 422
        assert first.get('/api/admin/risk/policy').json()['automatic_blocking'] is False


def test_failed_login_window_spans_attempt_sessions(app):
    class OnlyFailedWindow:
        def predict(self, events, **kwargs):
            assert len(events) == 6
            return {'random_forest':{'score':1}, 'isolation_forest':{'anomaly_evidence':1}}
    with TestClient(app) as client:
        app.state.detector, app.state.ml_status = OnlyFailedWindow(), 'ready'
        for _ in range(3):
            assert signin(client,password='wrong').status_code == 401
        with app.state.session_factory() as db:
            latest = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            evidence = json.loads(latest.evidence)
            assert evidence['ml']['predictions'][0]['context'] == 'failed_login_window'
            assert len(evidence['ml']['predictions'][0]['event_ids']) == 6
            assert db.get(User,1).risk_score > 45


def test_unattributed_and_admin_events_do_not_change_user_risk(app):
    with TestClient(app) as client:
        assert client.get('/api/bank/balance').status_code == 401
        signin(client,'admin','admin-test-password',True)
    with app.state.session_factory() as db:
        detection = db.scalar(select(DetectionResult))
        assert detection.user_id is None
        assert json.loads(detection.evidence)['scope'] == 'unattributed_event'
        assert not db.scalars(select(RiskScore)).all()
        assert all(user.risk_score == 0 for user in db.scalars(select(User)))


def test_decay_is_visible_at_rest_and_applied_to_next_event(app):
    with TestClient(app) as client:
        signin(client)
        with app.state.session_factory.begin() as db:
            user = db.get(User,1)
            user.risk_score = 80
            latest = db.scalar(select(RiskScore).order_by(RiskScore.id.desc()))
            latest.created_at = now()-timedelta(seconds=1200)
            assert current_risk(db,user,RiskPolicy(),at=latest.created_at+timedelta(seconds=600))['effective_score'] == 40
        client.get('/api/bank/balance')
        with app.state.session_factory() as db:
            assert db.get(User,1).risk_score == pytest.approx(20,abs=.01)


def test_optional_models_are_explicit_and_failures_preserve_events(app,tmp_path):
    assert load_detector(Settings(ml_enabled=False))[1] == 'disabled'
    assert load_detector(Settings(ml_model_directory=str(tmp_path)))[1] == 'artifacts_missing'
    (tmp_path/'artifact-manifest.json').write_text('not-json')
    assert load_detector(Settings(ml_model_directory=str(tmp_path)))[1] == 'artifacts_invalid'
    class Broken:
        def predict(self,*args,**kwargs):
            raise RuntimeError('inference failed')
    with TestClient(app) as client:
        app.state.detector, app.state.ml_status = Broken(), 'ready'
        signin(client)
        client.get('/api/bank/balance')
        assert client.get('/api/bank/history').status_code == 200
        with app.state.session_factory() as db:
            latest = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            evidence = json.loads(latest.evidence)
            assert evidence['ml']['status'] == 'inference_failed'
            assert evidence['contributions']['random_forest'] == 0
            assert evidence['ml_weights_renormalized'] is False


def test_window_expires_old_failures_and_bounds_observations(app):
    with TestClient(app) as client:
        for _ in range(3):
            signin(client,password='wrong')
        with app.state.session_factory.begin() as db:
            for row in db.scalars(select(SecurityEvent)):
                row.created_at = now()-timedelta(minutes=2)
        signin(client)
        client.get('/api/bank/balance')
        with app.state.session_factory() as db:
            latest = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            assert json.loads(latest.evidence)['behavior']['counts']['failed_logins'] == 0


def test_concurrent_updates_preserve_all_assessments(app):
    with TestClient(app) as client:
        signin(client)
        cookie = client.cookies.get('pg_bank')
        def action(_):
            browser = TestClient(app)
            browser.cookies.set('pg_bank',cookie)
            return browser.get('/api/bank/balance').status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(action,range(8))) == [200]*8
    with app.state.session_factory() as db:
        risks = db.scalars(select(RiskScore).order_by(RiskScore.id)).all()
        assert len(risks) == 10
        for previous,current in zip(risks,risks[1:]):
            assert current.previous_score == previous.score
        assert db.get(User,1).risk_score == risks[-1].score


def test_long_sessions_are_bounded_and_malformed_scores_are_explicit(app):
    class Malformed:
        def predict(self,*args,**kwargs):
            return {'random_forest':{'score':float('nan')},'isolation_forest':{'anomaly_evidence':1}}
    with TestClient(app) as client:
        app.state.settings = app.state.settings.model_copy(update={'risk_max_events':10})
        app.state.detector, app.state.ml_status = Malformed(), 'ready'
        signin(client)
        client.get('/api/bank/history')
        assert client.get('/api/bank/balance').status_code == 200
        with app.state.session_factory() as db:
            latest = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            assert json.loads(latest.evidence)['ml']['status'] == 'inference_failed'
        app.state.detector = ConstantDetector()
        for _ in range(9):
            client.get('/api/bank/balance')
        with app.state.session_factory() as db:
            latest = db.scalar(select(DetectionResult).order_by(DetectionResult.id.desc()))
            evidence = json.loads(latest.evidence)
            assert evidence['window']['truncated']
            assert len(evidence['window']['event_ids']) == 10
            assert 'session_event_limit' in evidence['ml']['skipped']


def test_risk_history_survives_application_restart(app):
    from app.main import create_app
    with TestClient(app) as client:
        signin(client)
        client.get('/api/bank/balance')
        with app.state.session_factory() as db:
            original = [(risk.id,risk.score) for risk in db.scalars(select(RiskScore).order_by(RiskScore.id))]
    reopened = create_app(app.state.settings)
    with TestClient(reopened) as admin:
        signin(admin,'admin','admin-test-password',True)
        response = admin.get('/api/admin/users/1/risk')
        assert response.status_code == 200
        assert [(entry['id'],entry['score']) for entry in reversed(response.json()['history'])] == original
