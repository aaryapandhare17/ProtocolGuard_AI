from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select,func
from app.main import create_app
from app.models.entities import (AdminAuditLog,BlockedEntity,DetectionResult,RiskReset,
    SecurityAlert,SecuritySettings,Session,User)
from test_auth import app,signin


def admin_login(client):
    response=signin(client,'admin','admin-test-password',True)
    assert response.status_code==200
    return {'X-CSRF-Token':response.json()['csrf_token']}


def action(client,path,headers,**extra):
    return client.post(path,headers=headers,json={'confirmed':True,'note':'Reviewed by administrator',**extra})


class Suspicious:
    def predict(self,*args,**kwargs):
        return {'random_forest':{'score':1},'isolation_forest':{'anomaly_evidence':1}}


def trigger(client,app):
    app.state.detector,app.state.ml_status=Suspicious(),'ready'
    signin(client)
    # Ten transfer requests make behavioral evidence > 15 points: total > 60.
    csrf=client.post('/api/auth/login',json={'username':'demo01','password':'bank-test-password'}).json()['csrf_token']
    for _ in range(15):
        response=client.post('/api/bank/transfer-request',headers={'X-CSRF-Token':csrf},json={'recipient':'Demo recipient','amount_cents':100})
        if response.status_code==403:
            return response
        assert response.status_code==200
    raise AssertionError('Expected automatic account block')


def test_automatic_block_revokes_all_sessions_and_denies_triggering_request(app):
    with TestClient(app) as first,TestClient(app) as second,TestClient(app) as other:
        signin(second)
        signin(other,'demo02')
        response=trigger(first,app)
        assert response.json()['detail']=='Account access restricted'
        assert first.get('/api/bank/balance').status_code==403
        assert second.get('/api/bank/history').status_code==403
        assert first.get('/api/auth/me').status_code==403
        assert other.get('/api/bank/balance').status_code==200
        with app.state.session_factory() as db:
            assert db.get(User,1).blocked
            assert not db.get(User,2).blocked
            assert all(session.revoked for session in db.scalars(select(Session).where(Session.user_id==1)))
            blocks=db.scalars(select(BlockedEntity)).all()
            assert len(blocks)==1 and blocks[0].active
            evidence=json.loads(blocks[0].evidence)
            assert evidence['score']>60 and evidence['threshold']==60
            assert db.get(DetectionResult,evidence['detection_id'])
            assert db.scalar(select(func.count()).select_from(SecurityAlert))==1
            assert db.scalar(select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.action=='AUTO_ACCOUNT_BLOCK'))==1


def test_threshold_is_strict_and_persistently_configurable(app):
    with TestClient(app) as bank,TestClient(app) as admin:
        headers=admin_login(admin)
        # Fake models contribute exactly 45 points while behavior is zero.
        assert action(admin,'/api/admin/settings/security',headers,block_threshold=45,auto_block_enabled=True).status_code==200
        app.state.detector,app.state.ml_status=Suspicious(),'ready'
        signin(bank)
        assert bank.get('/api/bank/balance').status_code==200
        assert bank.get('/api/bank/history').status_code==200
        with app.state.session_factory() as db:
            assert db.get(User,1).risk_score==45 and not db.get(User,1).blocked
        assert action(admin,'/api/admin/settings/security',headers,block_threshold=44,auto_block_enabled=True).status_code==200
        assert bank.get('/api/bank/balance').status_code==403
        assert admin.get('/api/admin/risk/policy').json()['threshold']==44
        reopened=create_app(app.state.settings)
        with TestClient(reopened) as fresh:
            admin_login(fresh)
            assert fresh.get('/api/admin/settings/security').json()['threshold']==44
            assert fresh.get('/api/admin/blocks?active=true').json()[0]['user_id']==1


def test_disable_automatic_policy_keeps_high_score_unblocked(app):
    with TestClient(app) as bank,TestClient(app) as admin:
        headers=admin_login(admin)
        action(admin,'/api/admin/settings/security',headers,block_threshold=10,auto_block_enabled=False)
        app.state.detector,app.state.ml_status=Suspicious(),'ready'
        signin(bank)
        bank.get('/api/bank/balance')
        assert bank.get('/api/bank/history').status_code==200
        with app.state.session_factory() as db:
            assert db.get(User,1).risk_score>=45 and not db.get(User,1).blocked
            assert not db.scalars(select(BlockedEntity)).all()


def test_manual_unblock_resets_baseline_without_restoring_sessions(app):
    with TestClient(app) as bank,TestClient(app) as admin:
        trigger(bank,app)
        old_cookie=bank.cookies.get('pg_bank')
        headers=admin_login(admin)
        response=action(admin,'/api/admin/users/1/unblock',headers)
        assert response.status_code==200 and response.json()['fresh_login_required']
        assert bank.get('/api/bank/balance').status_code==401
        with app.state.session_factory() as db:
            assert not db.get(User,1).blocked
            assert db.scalar(select(func.count()).select_from(RiskReset))==1
            assert all(session.revoked for session in db.scalars(select(Session).where(Session.user_id==1)))
            assert not db.scalar(select(BlockedEntity)).active
            assert db.scalar(select(SecurityAlert)).resolved_at
        assert signin(bank).status_code==200
        assert bank.cookies.get('pg_bank')!=old_cookie
        assert bank.get('/api/bank/balance').status_code==200
        assert action(admin,'/api/admin/users/1/unblock',headers).json()['changed'] is False
        # One reset only, even when an administrator repeats the request.
        with app.state.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(RiskReset))==1
        assert action(admin,'/api/admin/users/1/block',headers).status_code==200
        with app.state.session_factory() as db:
            assert len(db.scalars(select(BlockedEntity)).all())==2


def test_admin_controls_require_role_csrf_confirmation_and_notes(app):
    with TestClient(app) as client:
        body={'confirmed':True,'note':'Review complete'}
        assert client.post('/api/admin/users/1/block',json=body).status_code==401
        signin(client)
        assert client.get('/api/admin/alerts').status_code==401
        headers=admin_login(client)
        assert client.post('/api/admin/users/1/block',json=body).status_code==403
        for data in ({'confirmed':False,'note':'Review'}, {'confirmed':True,'note':'   '}, {'confirmed':1,'note':'Review'}):
            assert client.post('/api/admin/users/1/block',headers=headers,json=data).status_code==422
        assert action(client,'/api/admin/users/999/block',headers).status_code==404
        assert action(client,'/api/admin/users/1/block',headers).status_code==200
        assert action(client,'/api/admin/users/1/block',headers).json()['changed'] is False
        logs=client.get('/api/admin/audit-logs').json()
        assert {row['action'] for row in logs}>={'ACCOUNT_BLOCK','ACCOUNT_BLOCK_NOOP'}
        assert all(row['admin_id']==1 for row in logs)


def test_resolving_alert_does_not_unblock_account(app):
    with TestClient(app) as admin:
        headers=admin_login(admin)
        action(admin,'/api/admin/users/1/block',headers)
        alert=admin.get('/api/admin/alerts?unresolved=true').json()[0]
        response=action(admin,f"/api/admin/alerts/{alert['id']}/resolve",headers)
        assert response.json()['account_still_blocked']
        assert not admin.get('/api/admin/alerts?unresolved=true').json()
        assert action(admin,'/api/admin/alerts/999/resolve',headers).status_code==404


def test_concurrent_block_attempts_create_one_active_record(app):
    with TestClient(app) as admin:
        headers=admin_login(admin)
        cookie=admin.cookies.get('pg_admin')
        def block(_):
            client=TestClient(app)
            client.cookies.set('pg_admin',cookie)
            return action(client,'/api/admin/users/1/block',headers).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(block,range(4)))==[200]*4
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(BlockedEntity))==1
        assert db.scalar(select(func.count()).select_from(SecurityAlert))==1
        assert db.scalar(select(func.count()).select_from(AdminAuditLog))==4


def test_websocket_delivers_committed_alerts_and_reconnect_cursor(app):
    with TestClient(app) as admin:
        headers=admin_login(admin)
        with admin.websocket_connect('/ws/admin/events',headers={'origin':'http://localhost:5174'}) as ws:
            assert ws.receive_json()['type']=='connected'
            action(admin,'/api/admin/users/1/block',headers)
            message=ws.receive_json()
            assert message['type']=='security_alerts' and len(message['alerts'])==1
            cursor=message['cursor']
            assert message['alerts'][0]['user_id']==1
        with admin.websocket_connect(f'/ws/admin/events?after_id={cursor}') as ws:
            assert ws.receive_json()['cursor']==cursor
            ws.send_text('ping')
            assert ws.receive_json()['type']=='pong'
            action(admin,'/api/admin/users/2/block',headers)
            assert ws.receive_json()['alerts'][0]['user_id']==2


def test_websocket_rejects_untrusted_origins_and_revoked_admin_sessions(app):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect('/ws/admin/events'):
                pass
        assert error.value.code==4401
        headers=admin_login(client)
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect('/ws/admin/events',headers={'origin':'https://untrusted.example'}):
                pass
        assert error.value.code==4403
        with client.websocket_connect('/ws/admin/events') as ws:
            ws.receive_json()
            assert client.post('/api/admin/auth/logout',headers=headers).status_code==200
            with pytest.raises(WebSocketDisconnect) as error:
                while True:
                    ws.receive_json()
            assert error.value.code==4401


def test_banking_login_throttle_does_not_lock_out_administrator(app):
    with TestClient(app) as client:
        for _ in range(20):
            signin(client,username='unknown',password='wrong')
        assert signin(client).status_code==429
        assert signin(client,'admin','admin-test-password',True).status_code==200


def test_default_threshold_allows_60_and_blocks_above_60(app):
    with TestClient(app) as bank:
        app.state.detector,app.state.ml_status=Suspicious(),'ready'
        app.state.settings=app.state.settings.model_copy(update={
            'risk_fsm_weight':0,'risk_rf_weight':.60,'risk_if_weight':0,'risk_behavior_weight':.40})
        signin(bank)
        bank.get('/api/bank/balance')
        assert bank.get('/api/bank/history').status_code==200
        with app.state.session_factory() as db:
            assert db.get(User,1).risk_score==60
            assert not db.get(User,1).blocked
        app.state.settings=app.state.settings.model_copy(update={'risk_rf_weight':.61,'risk_behavior_weight':.39})
        assert bank.get('/api/bank/balance').status_code==403
        with app.state.session_factory() as db:
            evidence=json.loads(db.scalar(select(BlockedEntity)).evidence)
            assert evidence['score']==61 and evidence['threshold']==60


def test_concurrent_automatic_blocks_are_idempotent(app):
    with TestClient(app) as bank:
        signin(bank)
        bank.get('/api/bank/balance')
        app.state.detector,app.state.ml_status=Suspicious(),'ready'
        with app.state.session_factory.begin() as db:
            db.get(SecuritySettings,1).block_threshold=44
        cookie=bank.cookies.get('pg_bank')
        def request(_):
            client=TestClient(app)
            client.cookies.set('pg_bank',cookie)
            return client.get('/api/bank/balance').status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(request,range(8)))==[403]*8
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(BlockedEntity))==1
        assert db.scalar(select(func.count()).select_from(SecurityAlert))==1


def test_banking_action_to_live_automatic_alert(app):
    with TestClient(app) as bank,TestClient(app) as admin:
        admin_login(admin)
        with admin.websocket_connect('/ws/admin/events') as ws:
            assert ws.receive_json()['type']=='connected'
            trigger(bank,app)
            message=ws.receive_json()
            assert message['alerts'][0]['evidence']['score']>60
            assert message['alerts'][0]['evidence']['detection_id']
