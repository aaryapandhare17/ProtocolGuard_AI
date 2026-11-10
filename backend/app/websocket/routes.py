"""Authenticated, cursor-based delivery of committed security alerts."""
import asyncio
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from app.database.store import now
from app.models.entities import Admin, SecurityAlert, Session
from app.security.credentials import digest
from app.services.blocking import serialize_alert

router=APIRouter()


def authorized(ws,db):
    raw=ws.cookies.get("pg_admin","")
    session=db.get(Session,digest(raw)) if raw else None
    return bool(session and not session.revoked and session.expires_at>now() and session.admin_id and db.get(Admin,session.admin_id))


@router.websocket("/ws/admin/events")
async def alerts(ws:WebSocket,after_id:int=Query(0,ge=0)):
    origin=ws.headers.get("origin")
    if origin and origin not in ws.app.state.settings.cors_origins.split(","):
        await ws.close(code=4403)
        return
    with ws.app.state.session_factory() as db:
        valid=authorized(ws,db)
    if not valid:
        await ws.close(code=4401)
        return
    await ws.accept()
    cursor=after_id
    await ws.send_json({"type":"connected","cursor":cursor})
    try:
        while True:
            with ws.app.state.session_factory() as db:
                valid=authorized(ws,db)
                batch=[serialize_alert(row) for row in db.scalars(select(SecurityAlert).where(SecurityAlert.id>cursor)
                    .order_by(SecurityAlert.id).limit(100))] if valid else []
            if not valid:
                await ws.close(code=4401)
                return
            if batch:
                cursor=batch[-1]["id"]
                await ws.send_json({"type":"security_alerts","alerts":batch,"cursor":cursor})
                continue
            try:
                message=await asyncio.wait_for(ws.receive_text(),timeout=0.25)
                if message=="ping":
                    await ws.send_json({"type":"pong","cursor":cursor})
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
