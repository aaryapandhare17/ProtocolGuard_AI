import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from app.api.routes import admin_identity, database
from app.models.entities import DetectionResult, RiskScore, User
from app.security.risk import RiskPolicy
from app.services.risk import current_risk

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_identity)])


@router.get("/risk/policy")
def policy(request: Request):
    return {**RiskPolicy.from_settings(request.app.state.settings).describe(),
        "ml_status": request.app.state.ml_status, "automatic_blocking": False,
        "ip_risk_included": False, "score_note": "Risk index, not a probability"}


@router.get("/users/{user_id}/risk")
def user_risk(user_id: int, request: Request, limit: int = Query(default=50, ge=1, le=200), db=Depends(database)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    rows = db.execute(select(RiskScore, DetectionResult).join(DetectionResult, RiskScore.detection_id == DetectionResult.id)
        .where(RiskScore.user_id == user.id).order_by(RiskScore.id.desc()).limit(limit)).all()
    return {**current_risk(db, user, RiskPolicy.from_settings(request.app.state.settings)),
        "history": [{"id": risk.id, "event_id": detection.event_id, "score": risk.score,
            "created_at": risk.created_at.isoformat()+"Z", "evidence": json.loads(detection.evidence)} for risk, detection in rows]}
