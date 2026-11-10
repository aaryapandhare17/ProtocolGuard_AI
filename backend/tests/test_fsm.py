from itertools import product
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.fsm.engine import ALPHABET, STATES, definition, evaluate, step
from app.models.entities import SecurityEvent, Session
from test_auth import app, signin


@pytest.mark.parametrize('events', [
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'LOGOUT'],
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'VIEW_BALANCE', 'VIEW_BALANCE', 'VIEW_HISTORY',
     'TRANSFER_REQUEST', 'TRANSFER_RECORDED', 'VIEW_HISTORY', 'LOGOUT'],
    ['LOGIN_ATTEMPT', 'LOGIN_FAILED', 'LOGIN_ATTEMPT', 'LOGIN_SUCCESS',
     'TRANSFER_REQUEST', 'CANCEL_TRANSFER', 'VIEW_BALANCE', 'RETURN', 'LOGOUT'],
])
def test_complete_accepted_sequences(events):
    report = evaluate(events)
    assert report['accepted'] and report['valid_prefix']
    assert report['final_state'] == 'CLOSED'
    assert report['invalid_transition_count'] == 0


@pytest.mark.parametrize('events', [[], ['LOGIN_ATTEMPT'], ['LOGIN_ATTEMPT', 'LOGIN_FAILED'],
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'VIEW_HISTORY']])
def test_prefixes_are_not_complete_sessions(events):
    report = evaluate(events)
    assert report['valid_prefix'] and not report['accepted']
    assert report['classification'] == 'valid_prefix'


@pytest.mark.parametrize('events', [
    ['VIEW_BALANCE'], ['LOGIN_SUCCESS'],
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'TRANSFER_RECORDED'],
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'TRANSFER_REQUEST', 'TRANSFER_REQUEST'],
    ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'LOGOUT', 'VIEW_HISTORY'],
    ['UNAUTHORIZED_REQUEST', 'LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'LOGOUT'],
    ['NOT_IN_ALPHABET'],
])
def test_invalid_sequences_remain_rejected(events):
    report = evaluate(events)
    assert report['suspicious'] and not report['accepted'] and not report['valid_prefix']
    assert report['final_state'] == 'REJECTED'
    assert report['invalid_transition_count'] > 0
    assert all(v['explanation'] for v in report['violations'])


def test_total_deterministic_transition_function():
    table = definition()['transitions']
    assert len(table) == len(STATES) * len(ALPHABET)
    assert len({(row['from'], row['event']) for row in table}) == len(table)
    for state, event in product(STATES, ALPHABET):
        assert step(state, event).state_after in STATES
    with pytest.raises(ValueError):
        evaluate([], 'NOT_A_STATE')


def test_blocked_session_is_not_a_benign_prefix():
    report = evaluate(['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'BLOCK_ACCOUNT', 'ACCESS_BLOCKED'])
    assert report['final_state'] == 'BLOCKED'
    assert report['suspicious'] and not report['accepted'] and not report['valid_prefix']
    assert report['invalid_transition_count'] == 0


def admin_client(app):
    client = TestClient(app)
    assert signin(client, 'admin', 'admin-test-password', True).status_code == 200
    return client


def test_persisted_workflow_and_admin_replay(app):
    with TestClient(app) as bank:
        csrf = signin(bank).json()['csrf_token']
        bank.get('/api/bank/balance')
        bank.get('/api/bank/history')
        bank.post('/api/bank/transfer-request', json={'amount_cents':100, 'recipient':'demo'}, headers={'X-CSRF-Token':csrf})
        assert bank.post('/api/auth/logout', headers={'X-CSRF-Token':csrf}).status_code == 200
    with admin_client(app) as admin:
        sessions = admin.get('/api/admin/fsm/sessions').json()
        assert len(sessions) == 1
        assert sessions[0]['username'] == 'demo01'
        report = admin.get('/api/admin/fsm/sessions/'+sessions[0]['session_id']).json()
        assert report['accepted'] and report['complete_trace']
        assert report['events'] == ['LOGIN_ATTEMPT', 'LOGIN_SUCCESS', 'VIEW_BALANCE', 'VIEW_HISTORY',
                                   'TRANSFER_REQUEST', 'TRANSFER_RECORDED', 'LOGOUT']
        assert report['initial_state'] == 'LOGGED_OUT'
        for transition, persisted in zip(report['transitions'], report['persisted_events']):
            assert transition['state_before'] == persisted['state_before']
            assert transition['state_after'] == persisted['state_after']
            assert transition['valid'] == persisted['evidence']['valid']
        assert admin.get('/api/admin/fsm').status_code == 200
        assert admin.get('/api/admin/fsm/sessions/missing').status_code == 404
    with app.state.session_factory() as db:
        assert db.get(Session, sessions[0]['session_id']).state == 'CLOSED'


def test_failed_login_evidence_survives_denial(app):
    with TestClient(app) as bank:
        assert signin(bank, password='wrong').status_code == 401
        assert bank.get('/api/bank/balance').status_code == 401
    with app.state.session_factory() as db:
        rows = db.scalars(select(SecurityEvent).order_by(SecurityEvent.id)).all()
        assert [r.state_after for r in rows] == ['AUTHENTICATING', 'LOGGED_OUT', 'REJECTED']
        assert rows[0].session_id == rows[1].session_id
        assert rows[2].session_id is None
        assert json.loads(rows[2].evidence)['fsm']['valid'] is False


def test_sessions_stay_independent_for_same_account_and_shared_ip(app):
    with TestClient(app) as first, TestClient(app) as second, TestClient(app) as third:
        signin(first)
        signin(second)  # Same account, separate browser/session.
        signin(third, 'demo02')
        first.get('/api/bank/balance')
        with app.state.session_factory() as db:
            sessions = db.scalars(select(Session).order_by(Session.created_at)).all()
            assert [s.state for s in sessions] == ['VIEWING_ACCOUNT', 'AUTHENTICATED', 'AUTHENTICATED']
            assert len({s.id for s in sessions}) == 3


def test_analysis_cannot_grant_or_revoke_authorization(app):
    with TestClient(app) as bank:
        csrf = signin(bank).json()['csrf_token']
        with app.state.session_factory.begin() as db:
            session = db.scalar(select(Session).where(Session.user_id == 1))
            # A detected violation must not replace the authorization checks.
            session.state = 'REJECTED'
        assert bank.get('/api/bank/balance').status_code == 200
        with app.state.session_factory.begin() as db:
            session = db.scalar(select(Session).where(Session.user_id == 1))
            session.state = 'AUTHENTICATED'
            session.revoked = True
        assert bank.get('/api/bank/balance').status_code == 401
        assert bank.post('/api/auth/logout', headers={'X-CSRF-Token':csrf}).status_code == 401


def test_admin_apis_require_admin_and_exclude_admin_events(app):
    with TestClient(app) as client:
        assert client.get('/api/admin/fsm').status_code == 401
        signin(client)
        assert client.get('/api/admin/fsm/sessions').status_code == 401
    with admin_client(app) as client:
        assert len(client.get('/api/admin/fsm/sessions').json()) == 1
    with app.state.session_factory() as db:
        admin_events = db.scalars(select(SecurityEvent).where(SecurityEvent.endpoint.like('/api/admin/%'))).all()
        assert all('fsm' not in json.loads(e.evidence) for e in admin_events)


def test_legacy_events_are_preserved_and_marked_as_partial(app):
    with TestClient(app) as bank:
        signin(bank)
        with app.state.session_factory.begin() as db:
            events = db.scalars(select(SecurityEvent)).all()
            for event in events:
                event.evidence = '{}'
            session = db.scalar(select(Session))
            session_id = session.id
        bank.get('/api/bank/balance')
    with admin_client(app) as admin:
        report = admin.get('/api/admin/fsm/sessions/'+session_id).json()
        assert report['complete_trace'] is False
        assert report['initial_state'] == 'AUTHENTICATED'
        assert report['events'] == ['VIEW_BALANCE']
    with app.state.session_factory() as db:
        assert db.scalars(select(SecurityEvent).where(SecurityEvent.evidence == '{}')).all()


def test_parallel_actions_on_one_session_preserve_transitions(app):
    from concurrent.futures import ThreadPoolExecutor
    with TestClient(app) as bank:
        signin(bank)
        cookie = bank.cookies.get('pg_bank')

        def action(index):
            client = TestClient(app)
            client.cookies.set('pg_bank', cookie)
            return client.get('/api/bank/balance' if index % 2 else '/api/bank/history').status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(action, range(12))) == [200] * 12
    with app.state.session_factory() as db:
        rows = db.scalars(select(SecurityEvent).where(SecurityEvent.session_id.is_not(None)).order_by(SecurityEvent.id)).all()
        assert len(rows) == 14
        report = evaluate([row.event_type for row in rows])
        assert report['valid_prefix'] and not report['suspicious']
        assert all(row.state_after == transition['state_after'] for row, transition in zip(rows, report['transitions']))


def test_replay_survives_database_reopen(app):
    from app.main import create_app
    with TestClient(app) as bank:
        csrf = signin(bank).json()['csrf_token']
        bank.post('/api/auth/logout', headers={'X-CSRF-Token':csrf})
    reopened = create_app(app.state.settings)
    with TestClient(reopened) as admin:
        signin(admin, 'admin', 'admin-test-password', True)
        session_id = admin.get('/api/admin/fsm/sessions').json()[0]['session_id']
        report = admin.get('/api/admin/fsm/sessions/'+session_id).json()
        assert report['accepted'] and report['complete_trace']
