"""Independent IP observations, temporary restrictions and audited recovery."""
from collections import Counter
from datetime import timedelta
import json
from sqlalchemy import select,func
from app.database.store import now
from app.models.entities import IPAccount,IPRestriction,IPSecurityAlert,SecurityEvent,SuspiciousIP
from app.security.ip import canonical_ip
from app.services.blocking import audit

ABUSE_EVENTS=frozenset({'LOGIN_FAILED','UNAUTHORIZED_REQUEST','RATE_LIMIT_TRIGGERED'})


def ensure_ip(db,address,at=None):
    row=db.scalar(select(SuspiciousIP).where(SuspiciousIP.address==address))
    if not row:
        timestamp=at or now()
        row=SuspiciousIP(address=address,first_seen=timestamp,last_seen=timestamp)
        db.add(row)
        db.flush()
    return row


def recent_evidence(db,ip,config):
    rows=db.execute(select(SecurityEvent.id,SecurityEvent.event_type).where(
        SecurityEvent.ip==ip.address,SecurityEvent.created_at>=now()-timedelta(seconds=config.ip_abuse_window_seconds),
        SecurityEvent.id>ip.reset_event_id,SecurityEvent.event_type.in_(ABUSE_EVENTS))
        .order_by(SecurityEvent.id.desc()).limit(config.ip_abuse_threshold)).all()
    counts=Counter(row.event_type for row in rows)
    score=min(100,10*counts['LOGIN_FAILED']+20*counts['UNAUTHORIZED_REQUEST']+15*counts['RATE_LIMIT_TRIGGERED'])
    return {'score':score,'counts':dict(counts),'event_ids':[row.id for row in reversed(rows)],
        'unauthenticated_events':len(rows),'window_seconds':config.ip_abuse_window_seconds,
        'bounded_at':config.ip_abuse_threshold,'account_risk_included':False}


def clear_baseline(db,ip):
    ip.reset_event_id=db.scalar(select(func.max(SecurityEvent.id)).where(SecurityEvent.ip==ip.address)) or 0
    ip.risk_score=0


def resolve_alert(db,restriction):
    alert=db.scalar(select(IPSecurityAlert).where(IPSecurityAlert.restriction_id==restriction.id))
    if alert and not alert.resolved_at:
        alert.resolved_at=now()


def active_restriction(db,address):
    ip=db.scalar(select(SuspiciousIP).where(SuspiciousIP.address==address))
    if not ip:
        return None
    restriction=db.scalar(select(IPRestriction).where(IPRestriction.ip_id==ip.id,IPRestriction.active.is_(True)))
    if restriction and restriction.expires_at and restriction.expires_at<=now():
        restriction.active=False
        restriction.released_at=now()
        clear_baseline(db,ip)
        resolve_alert(db,restriction)
        audit(db,'IP_RESTRICTION_EXPIRED',ip_id=ip.id,address=address,restriction_id=restriction.id)
        db.flush()
        return None
    return restriction


def block_ip(db,ip,*,reason,source,evidence,admin_id=None,duration_seconds=None):
    restriction=active_restriction(db,ip.address)
    if restriction:
        if admin_id:
            audit(db,'IP_BLOCK_NOOP',admin_id=admin_id,ip_id=ip.id,address=ip.address,note=reason)
        return restriction,False
    restriction=IPRestriction(ip_id=ip.id,reason=reason,source=source,evidence=json.dumps(evidence),
        expires_at=now()+timedelta(seconds=duration_seconds) if duration_seconds else None)
    db.add(restriction)
    db.flush()
    db.add(IPSecurityAlert(ip_id=ip.id,restriction_id=restriction.id,reason=reason,evidence=json.dumps(evidence)))
    audit(db,'AUTO_IP_RESTRICT' if source=='automatic' else 'IP_BLOCK',admin_id=admin_id,
        ip_id=ip.id,address=ip.address,restriction_id=restriction.id,note=reason,evidence=evidence)
    db.flush()
    return restriction,True


def unblock_ip(db,ip,*,note,admin_id=None,actor='admin'):
    restriction=active_restriction(db,ip.address)
    if not restriction:
        audit(db,'IP_UNBLOCK_NOOP',admin_id=admin_id,ip_id=ip.id,address=ip.address,note=note,actor=actor)
        return False
    restriction.active=False
    restriction.released_at=now()
    clear_baseline(db,ip)
    resolve_alert(db,restriction)
    audit(db,'DEV_IP_RECOVERY' if actor=='development_cli' else 'IP_UNBLOCK',admin_id=admin_id,
        ip_id=ip.id,address=ip.address,restriction_id=restriction.id,note=note,actor=actor)
    db.flush()
    return True


def observe_event(db,request,event):
    try:
        address=canonical_ip(event.ip)
    except ValueError:
        return  # Non-network ASGI test clients have no numeric source address.
    ip=ensure_ip(db,address,at=event.created_at)
    ip.last_seen=event.created_at
    if event.user_id:
        edge=db.scalar(select(IPAccount).where(IPAccount.ip_id==ip.id,IPAccount.user_id==event.user_id))
        if not edge:
            edge=IPAccount(ip_id=ip.id,user_id=event.user_id,first_seen=event.created_at,last_seen=event.created_at)
            db.add(edge)
        edge.last_seen=event.created_at
    # Account blocks and their control markers never contribute to IP scoring.
    if event.event_type in ABUSE_EVENTS:
        ip.suspicious_count+=1
    evidence=recent_evidence(db,ip,request.app.state.settings)
    ip.risk_score=evidence['score']
    config=request.app.state.settings
    if config.ip_auto_restrict_enabled and evidence['unauthenticated_events']>=config.ip_abuse_threshold:
        block_ip(db,ip,reason='Repeated unauthenticated abuse exceeded the IP limit',source='automatic',
            evidence=evidence,duration_seconds=config.ip_restriction_seconds)


def serialize_alert(db,row):
    ip=db.get(SuspiciousIP,row.ip_id)
    return {'id':row.id,'ip_address':ip.address,'restriction_id':row.restriction_id,'severity':'high',
        'reason':row.reason,'evidence':json.loads(row.evidence),'created_at':row.created_at.isoformat()+'Z',
        'resolved_at':row.resolved_at.isoformat()+'Z' if row.resolved_at else None}
