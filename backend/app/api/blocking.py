import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from app.api.routes import admin_identity, database
from app.database.store import now
from app.models.entities import AdminAuditLog, BlockedEntity, SecurityAlert, SecuritySettings, User
from app.services.blocking import audit, block_account, serialize_alert, settings, unblock_account

router = APIRouter(prefix="/api/admin")


class ConfirmedAction(BaseModel):
    confirmed: bool = Field(strict=True)
    note: str = Field(min_length=3,max_length=500)
    @model_validator(mode="after")
    def validate_confirmation(self):
        self.note = self.note.strip()
        if not self.confirmed or len(self.note) < 3:
            raise ValueError("Explicit confirmation and a meaningful note are required")
        return self


class UnblockAction(ConfirmedAction):
    reset_risk: bool = Field(default=True,strict=True)


class SettingsAction(ConfirmedAction):
    block_threshold: float = Field(ge=0,le=100,allow_inf_nan=False)
    auto_block_enabled: bool = Field(strict=True)


def find_user(db,user_id):
    user = db.get(User,user_id)
    if not user:
        raise HTTPException(404,"User not found")
    return user


@router.post("/users/{user_id}/block")
def block(user_id:int, data:ConfirmedAction, request:Request, auth=Depends(admin_identity), db=Depends(database)):
    user = find_user(db,user_id)
    row,changed = block_account(db,request,user,reason=data.note,source="manual",
        evidence={"admin_id":auth[0].id,"note":data.note},admin_id=auth[0].id)
    return {"user_id":user.id,"blocked":True,"block_id":row.id,"changed":changed}


@router.post("/users/{user_id}/unblock")
def unblock(user_id:int, data:UnblockAction, request:Request, auth=Depends(admin_identity), db=Depends(database)):
    user = find_user(db,user_id)
    changed = unblock_account(db,request,user,auth[0].id,data.note,data.reset_risk)
    return {"user_id":user.id,"blocked":False,"changed":changed,"fresh_login_required":True}


@router.get("/blocks")
def blocks(user_id:int|None=None, active:bool|None=None, limit:int=Query(50,ge=1,le=200), auth=Depends(admin_identity), db=Depends(database)):
    query=select(BlockedEntity)
    if user_id is not None:
        query=query.where(BlockedEntity.user_id==user_id)
    if active is not None:
        query=query.where(BlockedEntity.active==active)
    rows=db.scalars(query.order_by(BlockedEntity.id.desc()).limit(limit)).all()
    return [{"id":row.id,"user_id":row.user_id,"entity_type":row.entity_type,"active":row.active,
        "source":row.source,"reason":row.reason,"evidence":json.loads(row.evidence),
        "created_at":row.created_at.isoformat()+"Z","released_at":row.released_at.isoformat()+"Z" if row.released_at else None} for row in rows]


@router.get("/alerts")
def alerts(limit:int=Query(50,ge=1,le=200), unresolved:bool=False, auth=Depends(admin_identity),db=Depends(database)):
    query=select(SecurityAlert)
    if unresolved:
        query=query.where(SecurityAlert.resolved_at.is_(None))
    return [serialize_alert(row) for row in db.scalars(query.order_by(SecurityAlert.id.desc()).limit(limit))]


@router.post("/alerts/{alert_id}/resolve")
def resolve(alert_id:int,data:ConfirmedAction,auth=Depends(admin_identity),db=Depends(database)):
    alert=db.get(SecurityAlert,alert_id)
    if not alert:
        raise HTTPException(404,"Alert not found")
    if alert.resolved_at is None:
        alert.resolved_at,alert.resolved_by=now(),auth[0].id
    audit(db,"ALERT_RESOLVE",alert.user_id,auth[0].id,alert_id=alert.id,note=data.note)
    return {"id":alert.id,"resolved":True,"account_still_blocked":db.get(User,alert.user_id).blocked}


@router.get("/settings/security")
def get_settings(request:Request,auth=Depends(admin_identity),db=Depends(database)):
    return settings(db,request.app.state.settings)


@router.post("/settings/security")
def update_settings(data:SettingsAction,auth=Depends(admin_identity),db=Depends(database)):
    row=db.get(SecuritySettings,1)
    before={"threshold":row.block_threshold,"automatic_blocking":row.auto_block_enabled}
    row.block_threshold,row.auto_block_enabled=data.block_threshold,data.auto_block_enabled
    audit(db,"SECURITY_SETTINGS_UPDATE",admin_id=auth[0].id,note=data.note,before=before,
        after={"threshold":data.block_threshold,"automatic_blocking":data.auto_block_enabled})
    return {"threshold":row.block_threshold,"automatic_blocking":row.auto_block_enabled}


@router.get("/audit-logs")
def audit_logs(limit:int=Query(50,ge=1,le=200),auth=Depends(admin_identity),db=Depends(database)):
    return [{"id":row.id,"admin_id":row.admin_id,"user_id":row.user_id,"action":row.action,
        "evidence":json.loads(row.evidence),"created_at":row.created_at.isoformat()+"Z"}
        for row in db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(limit))]
