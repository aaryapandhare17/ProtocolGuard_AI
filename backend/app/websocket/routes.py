"""Authenticated, cursor-based delivery of committed account and IP alerts."""
import asyncio
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from app.database.store import now
from app.models.entities import Admin, SecurityAlert, Session, IPSecurityAlert
from app.security.credentials import digest
from app.services.blocking import serialize_alert
from app.services.ips import active_restriction, serialize_alert as serialize_ip_alert
from app.security.ip import connection_ip

router=APIRouter()


def authorized(ws,db):
    raw=ws.cookies.get('pg_admin','')
    session=db.get(Session,digest(raw)) if raw else None
    return bool(session and not session.revoked and session.expires_at>now() and session.admin_id and db.get(Admin,session.admin_id))


def poll(ws,cursor,ip_cursor):
    # This runs in a worker: SQLite transaction waits never stall the event loop.
    with ws.app.state.session_factory() as db:
        address=connection_ip(ws.scope)
        if address and db.bind.dialect.name=='sqlite':
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        denied=bool(active_restriction(db,address)) if address else False
        valid=authorized(ws,db) and not denied
        ip_batch=[serialize_ip_alert(db,row) for row in db.scalars(select(IPSecurityAlert).where(IPSecurityAlert.id>ip_cursor)
            .order_by(IPSecurityAlert.id).limit(100))] if valid else []
        batch=[serialize_alert(row) for row in db.scalars(select(SecurityAlert).where(SecurityAlert.id>cursor)
            .order_by(SecurityAlert.id).limit(100))] if valid else []
        db.commit()
        return valid,denied,batch,ip_batch


@router.websocket('/ws/admin/events')
async def alerts(ws:WebSocket,after_id:int=Query(0,ge=0),after_ip_id:int=Query(0,ge=0)):
    origin=ws.headers.get('origin')
    if origin and origin not in ws.app.state.settings.cors_origins.split(','):
        await ws.close(code=4403)
        return
    valid,denied,_,_=await run_in_threadpool(poll,ws,after_id,after_ip_id)
    if not valid:
        await ws.close(code=4403 if denied else 4401)
        return
    await ws.accept()
    cursor,ip_cursor=after_id,after_ip_id
    await ws.send_json({'type':'connected','cursor':cursor,'ip_cursor':ip_cursor})
    try:
        while True:
            valid,denied,batch,ip_batch=await run_in_threadpool(poll,ws,cursor,ip_cursor)
            if not valid:
                await ws.close(code=4403 if denied else 4401)
                return
            if ip_batch:
                ip_cursor=ip_batch[-1]['id']
                await ws.send_json({'type':'ip_security_alerts','alerts':ip_batch,'ip_cursor':ip_cursor})
            if batch:
                cursor=batch[-1]['id']
                await ws.send_json({'type':'security_alerts','alerts':batch,'cursor':cursor})
            if batch or ip_batch:
                continue
            try:
                message=await asyncio.wait_for(ws.receive(),timeout=0.25)
                if message['type']=='websocket.disconnect':
                    return
                if message.get('bytes') is not None:
                    await ws.close(code=1003)
                    return
                if message.get('text')=='ping':
                    await ws.send_json({'type':'pong','cursor':cursor,'ip_cursor':ip_cursor})
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
