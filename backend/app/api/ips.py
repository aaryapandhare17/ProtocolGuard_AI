import json
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import Field,field_validator
from sqlalchemy import select,or_,exists
from app.api.routes import admin_identity,database
from app.api.blocking import ConfirmedAction
from app.models.entities import IPAccount,IPRestriction,IPSecurityAlert,SecurityEvent,SuspiciousIP
from app.security.ip import canonical_ip,connection_ip
from app.services.ips import (active_restriction,block_ip,ensure_ip,recent_evidence,serialize_alert,unblock_ip)

router=APIRouter(prefix='/api/admin')


class IPAction(ConfirmedAction):
    ip_address:str=Field(max_length=45)
    @field_validator('ip_address')
    @classmethod
    def address(cls,value):
        return canonical_ip(value)


class IPBlockAction(IPAction):
    duration_seconds:int|None=Field(default=None,ge=5,le=86400,strict=True)


def description(db,ip,config):
    restriction=active_restriction(db,ip.address)
    evidence=recent_evidence(db,ip,config)
    return {'id':ip.id,'ip_address':ip.address,'first_seen':ip.first_seen.isoformat()+'Z',
        'last_seen':ip.last_seen.isoformat()+'Z','suspicious_event_count':ip.suspicious_count,
        'risk_score':evidence['score'],'stored_risk_score':ip.risk_score,'risk_evidence':evidence,
        'associated_user_ids':list(db.scalars(select(IPAccount.user_id).where(IPAccount.ip_id==ip.id))),
        'blocked':bool(restriction),'restriction_id':restriction.id if restriction else None,
        'block_reason':restriction.reason if restriction else None,
        'expires_at':restriction.expires_at.isoformat()+'Z' if restriction and restriction.expires_at else None}


@router.get('/suspicious-ips')
def ips(request:Request,suspicious_only:bool=True,limit:int=Query(50,ge=1,le=200),auth=Depends(admin_identity),db=Depends(database)):
    query=select(SuspiciousIP)
    if suspicious_only:
        query=query.where(or_(SuspiciousIP.suspicious_count>0,exists(select(IPRestriction.id).where(
            IPRestriction.ip_id==SuspiciousIP.id,IPRestriction.active.is_(True)))))
    return [description(db,ip,request.app.state.settings) for ip in db.scalars(query.order_by(SuspiciousIP.last_seen.desc()).limit(limit))]


@router.get('/suspicious-ips/{ip_id}')
def detail(ip_id:int,request:Request,limit:int=Query(50,ge=1,le=200),auth=Depends(admin_identity),db=Depends(database)):
    ip=db.get(SuspiciousIP,ip_id)
    if not ip:
        raise HTTPException(404,'IP record not found')
    events=db.scalars(select(SecurityEvent).where(SecurityEvent.ip==ip.address).order_by(SecurityEvent.id.desc()).limit(limit)).all()
    restrictions=db.scalars(select(IPRestriction).where(IPRestriction.ip_id==ip.id).order_by(IPRestriction.id.desc()).limit(limit)).all()
    return {**description(db,ip,request.app.state.settings),
        'events':[{'id':row.id,'user_id':row.user_id,'type':row.event_type,'outcome':row.outcome,
            'created_at':row.created_at.isoformat()+'Z'} for row in events],
        'restrictions':[{'id':row.id,'active':row.active,'source':row.source,'reason':row.reason,
            'evidence':json.loads(row.evidence),'created_at':row.created_at.isoformat()+'Z',
            'released_at':row.released_at.isoformat()+'Z' if row.released_at else None} for row in restrictions]}


@router.post('/ips/block')
def block(data:IPBlockAction,request:Request,auth=Depends(admin_identity),db=Depends(database)):
    ip=ensure_ip(db,data.ip_address)
    restriction,changed=block_ip(db,ip,reason=data.note,source='manual',admin_id=auth[0].id,
        evidence={'admin_id':auth[0].id,'note':data.note},duration_seconds=data.duration_seconds)
    return {'ip_address':ip.address,'blocked':True,'restriction_id':restriction.id,'changed':changed,
        'affects_current_connection':connection_ip(request.scope)==ip.address}


@router.post('/ips/unblock')
def unblock(data:IPAction,auth=Depends(admin_identity),db=Depends(database)):
    ip=db.scalar(select(SuspiciousIP).where(SuspiciousIP.address==data.ip_address))
    if not ip:
        raise HTTPException(404,'IP record not found')
    changed=unblock_ip(db,ip,note=data.note,admin_id=auth[0].id)
    return {'ip_address':ip.address,'blocked':False,'changed':changed}


@router.get('/ip-alerts')
def alerts(limit:int=Query(50,ge=1,le=200),auth=Depends(admin_identity),db=Depends(database)):
    return [serialize_alert(db,row) for row in db.scalars(select(IPSecurityAlert).order_by(IPSecurityAlert.id.desc()).limit(limit))]
