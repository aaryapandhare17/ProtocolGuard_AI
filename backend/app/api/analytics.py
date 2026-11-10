import json
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from app.api.routes import admin_identity, database
from app.models.entities import DetectionResult, SecurityEvent, User
from app.services.analytics import saved_evaluation, saved_comparison
from app.security.risk import RiskPolicy
from app.services.blocking import settings

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_identity)])


@router.get("/ml/metrics")
def metrics(request: Request):
    return saved_evaluation(request.app)


@router.get("/detectors/comparison")
def comparison(request: Request, db=Depends(database)):
    response = saved_comparison(request.app)
    if response["status"] == "available":
        report = response["report"]
        response["runtime_policy_match"] = (
            report["policy"]
            == RiskPolicy.from_settings(request.app.state.settings).describe()
            and report["hybrid_threshold"]
            == settings(db, request.app.state.settings)["threshold"]
        )
    return response


@router.get("/ml/predictions")
def predictions(limit: int = Query(100, ge=1, le=200), db=Depends(database)):
    rows = db.execute(
        select(DetectionResult, SecurityEvent, User.username)
        .join(SecurityEvent, DetectionResult.event_id == SecurityEvent.id)
        .outerjoin(User, DetectionResult.user_id == User.id)
        .order_by(DetectionResult.id.desc())
        .limit(limit)
    ).all()
    result = []
    for detection, event, username in rows:
        evidence = json.loads(detection.evidence)
        ml = evidence.get("ml", {})
        for item in ml.get("predictions", []):
            prediction = item["prediction"]
            result.append(
                {
                    "detection_id": detection.id,
                    "event_id": event.id,
                    "user_id": event.user_id,
                    "username": username,
                    "created_at": detection.created_at.isoformat() + "Z",
                    "context": item["context"],
                    "risk_score": evidence["score"],
                    "random_forest": prediction["random_forest"],
                    "isolation_forest": prediction["isolation_forest"],
                    "provisional": prediction.get("provisional", True),
                }
            )
    return {
        "assessments_scanned": len(rows),
        "predictions": result,
        "scope": "Bounded recent persisted assessments; may include multiple contexts per assessment. Not a complete population.",
    }
