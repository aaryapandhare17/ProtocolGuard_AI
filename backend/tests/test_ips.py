from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select,func
from app.database.store import now
from app.main import create_app
from app.models.entities import AdminAuditLog,IPAccount,IPRestriction,IPSecurityAlert,SecurityEvent,SuspiciousIP,User
from app.recover_ip import recover
from app.security.ip import canonical_ip
from test_auth import app,signin
from test_blocking import admin_login,action

BANK_IP='198.51.100.10'
ADMIN_IP='198.51.100.20'


def ip_action(client,headers,path,address=BANK_IP,**extra):
    return action(client,path,headers,ip_address=address,**extra)


def test_ip_history_associations_and_header_spoofing(app):
    with TestClient(app,client=(BANK_IP,5000)) as bank,TestClient(app,client=(ADMIN_IP,5001)) as admin:
        signin(bank)
        bank.get('/api/bank/balance')
        signin(bank,'demo02',password='wrong')
        headers=admin_login(admin)
        rows=admin.get('/api/admin/suspicious-ips').json()
        assert len(rows)==1
        record=rows[0]
        assert record['ip_address']==BANK_IP and record['associated_user_ids']==[1,2]
        assert record['suspicious_event_count']==1 and record['risk_score']==10
        detail=admin.get(f"/api/admin/suspicious-ips/{record['id']}").json()
        assert len(detail['events'])==5
        assert detail['risk_evidence']['account_risk_included'] is False
        ip_action(admin,headers,'/api/admin/ips/block',address='203.0.113.99')
        # Arbitrary forwarded headers cannot change the trusted connection IP.
        assert bank.get('/api/bank/balance',headers={'X-Forwarded-For':'203.0.113.99','Forwarded':'for=203.0.113.99'}).status_code==200
        ip_action(admin,headers,'/api/admin/ips/block')
        assert bank.get('/api/bank/balance',headers={'X-Forwarded-For':ADMIN_IP}).status_code==403
        with app.state.session_factory() as db:
            event=db.scalar(select(SecurityEvent).order_by(SecurityEvent.id.desc()))
            assert event.ip==BANK_IP and json.loads(event.evidence)['scope']=='gateway'


def test_account_and_ip_unblock_are_independent(app):
    with TestClient(app,client=(BANK_IP,5000)) as first,TestClient(app,client=(BANK_IP,5001)) as second,TestClient(app,client=(ADMIN_IP,5002)) as admin:
        signin(first)
        signin(second,'demo02')
        headers=admin_login(admin)
        action(admin,'/api/admin/users/1/block',headers)
        assert first.get('/api/bank/balance').status_code==403
        assert second.get('/api/bank/balance').status_code==200
        with app.state.session_factory() as db:
            assert not db.scalars(select(IPRestriction)).all()
        ip_action(admin,headers,'/api/admin/ips/block')
        assert second.get('/api/bank/balance').status_code==403
        action(admin,'/api/admin/users/1/unblock',headers)
        assert first.get('/api/bank/balance').json()['detail']=='IP access restricted'
        action(admin,'/api/admin/users/1/block',headers)
        ip_action(admin,headers,'/api/admin/ips/unblock')
        assert first.get('/api/bank/balance').json()['detail']=='Account access restricted'
        assert second.get('/api/bank/balance').status_code==200
        with app.state.session_factory() as db:
            assert db.get(User,1).blocked and not db.get(User,2).blocked


def test_temporary_unauthenticated_restriction_expires_and_resets_baseline(app):
    app.state.settings=app.state.settings.model_copy(update={'ip_abuse_threshold':5})
    with TestClient(app,client=(BANK_IP,5000)) as bank:
        for _ in range(5):
            assert bank.get('/api/bank/balance').status_code==401
        assert bank.get('/api/auth/me').status_code==403
        assert bank.get('/api/health').status_code==200
        assert bank.get('/docs').status_code==403
        with app.state.session_factory.begin() as db:
            restriction=db.scalar(select(IPRestriction))
            assert restriction.source=='automatic' and restriction.expires_at
            restriction.expires_at=now()-timedelta(seconds=1)
        assert bank.get('/api/bank/balance').status_code==401
        with app.state.session_factory() as db:
            restriction=db.scalar(select(IPRestriction))
            assert not restriction.active and restriction.released_at
            assert db.scalar(select(IPSecurityAlert)).resolved_at
            assert db.scalar(select(SuspiciousIP)).reset_event_id>0
        # Previous failures must not immediately recreate the expired restriction.
        assert signin(bank).status_code==200


def test_manual_restriction_gateway_applies_to_admin_and_websockets_and_recovers_locally(app):
    with TestClient(app,client=(ADMIN_IP,5000)) as admin:
        headers=admin_login(admin)
        response=ip_action(admin,headers,'/api/admin/ips/block',address=ADMIN_IP)
        assert response.json()['affects_current_connection']
        assert admin.get('/api/admin/alerts').status_code==403
        assert signin(admin,'admin','admin-test-password',True).status_code==403
        with pytest.raises(WebSocketDisconnect) as error:
            with admin.websocket_connect('/ws/admin/events'):
                pass
        assert error.value.code==4403
        with pytest.raises(PermissionError):
            recover(app.state.session_factory,ADMIN_IP,'Recovery review',environment='production',confirmed=True)
        with pytest.raises(ValueError):
            recover(app.state.session_factory,ADMIN_IP,'Recovery review',environment='development')
        assert recover(app.state.session_factory,ADMIN_IP,'Recovery review',environment='development',confirmed=True)
        assert admin.get('/api/admin/alerts').status_code==200
        logs=admin.get('/api/admin/audit-logs').json()
        assert any(row['action']=='DEV_IP_RECOVERY' for row in logs)


def test_ip_endpoints_require_admin_csrf_valid_address_and_confirmation(app):
    with TestClient(app,client=(ADMIN_IP,5000)) as client:
        assert client.get('/api/admin/suspicious-ips').status_code==401
        headers=admin_login(client)
        body={'confirmed':True,'note':'Reviewed address','ip_address':BANK_IP}
        assert client.post('/api/admin/ips/block',json=body).status_code==403
        for address in ('not-an-ip','198.51.100.0/24','127.0.0.1:80','fe80::1%eth0'):
            assert ip_action(client,headers,'/api/admin/ips/block',address=address).status_code==422
        assert client.post('/api/admin/ips/block',headers=headers,json={**body,'confirmed':False}).status_code==422
        assert ip_action(client,headers,'/api/admin/ips/unblock',address='203.0.113.55').status_code==404
        assert ip_action(client,headers,'/api/admin/ips/block',address='::ffff:198.51.100.10').json()['ip_address']==BANK_IP
        assert ip_action(client,headers,'/api/admin/ips/block').json()['changed'] is False
        assert ip_action(client,headers,'/api/admin/ips/unblock').json()['changed']
        assert ip_action(client,headers,'/api/admin/ips/unblock').json()['changed'] is False
        assert client.get('/api/admin/suspicious-ips/999').status_code==404


def test_ip_restrictions_persist_and_concurrent_actions_deduplicate(app):
    with TestClient(app,client=(ADMIN_IP,5000)) as admin:
        headers=admin_login(admin)
        cookie=admin.cookies.get('pg_admin')
        def block(_):
            client=TestClient(app,client=(ADMIN_IP,5001))
            client.cookies.set('pg_admin',cookie)
            return ip_action(client,headers,'/api/admin/ips/block').status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert list(pool.map(block,range(4)))==[200]*4
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(IPRestriction))==1
        assert db.scalar(select(func.count()).select_from(IPSecurityAlert))==1
    reopened=create_app(app.state.settings)
    with TestClient(reopened,client=(BANK_IP,5000)) as bank:
        assert bank.get('/api/bank/balance').status_code==403


def test_live_ip_alert_cursor_and_existing_stream_restriction(app):
    with TestClient(app,client=(ADMIN_IP,5000)) as admin,TestClient(app,client=(BANK_IP,5001)) as second_admin:
        headers=admin_login(admin)
        admin_login(second_admin)
        with admin.websocket_connect('/ws/admin/events') as ws,second_admin.websocket_connect('/ws/admin/events') as other:
            ws.receive_json();other.receive_json()
            ip_action(admin,headers,'/api/admin/ips/block')
            message=ws.receive_json()
            assert message['type']=='ip_security_alerts' and message['alerts'][0]['ip_address']==BANK_IP
            cursor=message['ip_cursor']
            with pytest.raises(WebSocketDisconnect) as error:
                other.receive_json()
            assert error.value.code==4403
        with admin.websocket_connect(f'/ws/admin/events?after_ip_id={cursor}') as ws:
            assert ws.receive_json()['ip_cursor']==cursor
            ws.send_text('ping')
            assert ws.receive_json()['type']=='pong'


def test_ipv6_canonicalization_and_disabled_auto_restriction(app):
    assert canonical_ip('2001:0DB8:0:0:0:0:0:1')=='2001:db8::1'
    assert canonical_ip('::ffff:192.0.2.1')=='192.0.2.1'
    app.state.settings=app.state.settings.model_copy(update={'ip_auto_restrict_enabled':False,'ip_abuse_threshold':5})
    with TestClient(app,client=('2001:db8::1',5000)) as client:
        for _ in range(6):
            assert client.get('/api/bank/balance').status_code==401
        with app.state.session_factory() as db:
            ip=db.scalar(select(SuspiciousIP))
            assert ip.address=='2001:db8::1' and ip.suspicious_count==6
            assert not db.scalars(select(IPRestriction)).all()


def test_concurrent_requests_share_one_event_loop_without_gateway_deadlock(app):
    with TestClient(app,client=(BANK_IP,5000)) as bank:
        signin(bank)
        def balance(_):
            return bank.get('/api/bank/balance').status_code
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(balance,range(12)))==[200]*12
        with app.state.session_factory() as db:
            assert len(db.scalars(select(IPAccount)).all())==1


def test_explicit_recovery_does_not_release_account_block(app):
    with TestClient(app,client=(ADMIN_IP,5000)) as admin,TestClient(app,client=(BANK_IP,5001)) as bank:
        headers=admin_login(admin)
        signin(bank)
        action(admin,'/api/admin/users/1/block',headers)
        ip_action(admin,headers,'/api/admin/ips/block')
        assert recover(app.state.session_factory,BANK_IP,'Reviewed local restriction',environment='development',confirmed=True)
        assert bank.get('/api/bank/balance').json()['detail']=='Account access restricted'
