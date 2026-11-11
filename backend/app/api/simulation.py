import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import select

from app.api.blocking import ConfirmedAction
from app.api.routes import admin_identity, database
from app.database.store import now
from app.models.entities import SimulationRun, User
from app.security.risk import RiskPolicy
from app.services.blocking import audit, settings
from app.services.simulation import DEMO_ACCOUNTS, SCENARIOS, run_sandbox

router = APIRouter(prefix="/api/simulation")
logger = logging.getLogger(__name__)


class SimulationAction(ConfirmedAction):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal[
        "normal",
        "failed_logins",
        "unauthorized",
        "rapid_requests",
        "transfer_burst",
        "mixed",
    ]
    accounts: list[str] = Field(min_length=1, max_length=10)
    seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    shared_ip: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def demo_only(self):
        if len(set(self.accounts)) != len(self.accounts) or any(
            account not in DEMO_ACCOUNTS for account in self.accounts
        ):
            raise ValueError("Choose unique provisioned demo01–demo10 accounts only")
        return self


def enabled(config):
    return config.simulation_enabled and config.protocolguard_env == "development"


def projection(row, include_result=False):
    result = json.loads(row.result)
    return {
        "id": row.id,
        "scenario": row.scenario,
        "status": row.status,
        "configuration": json.loads(row.configuration),
        "started_at": row.started_at.isoformat() + "Z",
        "finished_at": row.finished_at.isoformat() + "Z" if row.finished_at else None,
        "summary": result.get("summary"),
        **({"result": result} if include_result else {}),
    }


@router.get("/scenarios")
def catalog(request: Request, auth=Depends(admin_identity), db=Depends(database)):
    names = list(
        db.scalars(
            select(User.username)
            .where(User.username.in_(DEMO_ACCOUNTS))
            .order_by(User.username)
        )
    )
    return {
        "enabled": enabled(request.app.state.settings),
        "scenarios": [{"id": key, **value} for key, value in SCENARIOS.items()],
        "accounts": names,
        "max_actors": 10,
        "max_concurrent_runs": 2,
        "scope": "isolated_demo_clones",
    }


@router.post("/run")
async def run(
    data: SimulationAction,
    request: Request,
    auth=Depends(admin_identity),
    db=Depends(database),
):
    if not enabled(request.app.state.settings):
        raise HTTPException(
            403, "Simulation lab is available only in enabled development environments"
        )
    provisioned = set(
        db.scalars(select(User.username).where(User.username.in_(data.accounts)))
    )
    if provisioned != set(data.accounts):
        raise HTTPException(400, "One or more demo accounts have not been provisioned")
    if not request.app.state.simulation_slots.acquire(blocking=False):
        raise HTTPException(
            409, "Two simulations are already running. Try again when one finishes."
        )
    run_id = uuid.uuid4().hex
    try:
        enforcement = settings(db, request.app.state.settings)
        configuration = {
            "accounts": data.accounts,
            "seed": data.seed,
            "shared_ip": data.shared_ip,
            "note": data.note,
            "policy": RiskPolicy.from_settings(request.app.state.settings).describe(),
            "enforcement": enforcement,
            "model_status": request.app.state.ml_status,
            "model_sha256": getattr(
                request.app.state.detector, "artifact_sha256", None
            ),
        }
        record = SimulationRun(
            id=run_id,
            admin_id=auth[0].id,
            scenario=data.scenario,
            configuration=json.dumps(configuration),
        )
        db.add(record)
        audit(
            db,
            "SIMULATION_START",
            admin_id=auth[0].id,
            run_id=run_id,
            scenario=data.scenario,
            accounts=data.accounts,
            note=data.note,
        )
        db.commit()  # Release the live SQLite write lock while isolated actors execute.
        try:
            result = await run_sandbox(
                request.app,
                data.accounts,
                data.scenario,
                data.seed,
                data.shared_ip,
                enforcement,
            )
            status = (
                "completed_with_errors"
                if any(actor["status"] == "failed" for actor in result["actors"])
                else "completed"
            )
        except Exception as error:
            logger.warning("Simulation failed (%s)", type(error).__name__)
            result = {
                "error": f"Simulation could not complete ({type(error).__name__})."
            }
            status = "failed"
        if db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        record.result = json.dumps(result, allow_nan=False)
        record.status = status
        record.finished_at = now()
        audit(
            db,
            "SIMULATION_COMPLETE" if status == "completed" else "SIMULATION_FAILED",
            admin_id=auth[0].id,
            run_id=run_id,
            status=status,
        )
        db.flush()
        db.refresh(auth[1])
        if auth[1].revoked or auth[1].expires_at <= now():
            raise HTTPException(
                401,
                "Administrator session expired or was revoked; sign in to inspect the saved run",
            )
        return projection(record, True)
    finally:
        request.app.state.simulation_slots.release()


@router.get("/runs")
def runs(
    limit: int = Query(25, ge=1, le=100),
    auth=Depends(admin_identity),
    db=Depends(database),
):
    return [
        projection(row)
        for row in db.scalars(
            select(SimulationRun).order_by(SimulationRun.started_at.desc()).limit(limit)
        )
    ]


@router.get("/runs/{run_id}")
def detail(run_id: str, auth=Depends(admin_identity), db=Depends(database)):
    record = db.get(SimulationRun, run_id)
    if not record:
        raise HTTPException(404, "Simulation run not found")
    return projection(record, True)
