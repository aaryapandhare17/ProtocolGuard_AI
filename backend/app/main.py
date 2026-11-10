from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.store import Base, configure
from app.api.routes import router
from app.api.fsm import router as fsm_router
from app.api.risk import router as risk_router
from app.services.risk import load_detector
from app.api.blocking import router as blocking_router
from app.websocket.routes import router as websocket_router
from app.models.entities import SecuritySettings


def create_app(config=None) -> FastAPI:
    config = config or settings
    engine, factory = configure(config.database_url)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        with factory.begin() as db:
            if not db.get(SecuritySettings,1):
                db.add(SecuritySettings(id=1,block_threshold=config.block_threshold,auto_block_enabled=config.auto_block_enabled))
        app.state.detector, app.state.ml_status = load_detector(config)
        yield
        engine.dispose()

    app = FastAPI(title="ProtocolGuard AI", version="0.2.0", lifespan=lifespan)
    app.state.detector = None
    app.state.ml_status = "not_initialized"
    app.state.settings = config
    app.state.session_factory = factory
    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins.split(","),
        allow_credentials=True, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"])
    app.include_router(router)
    app.include_router(fsm_router)
    app.include_router(risk_router)
    app.include_router(blocking_router)
    app.include_router(websocket_router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "protocolguard-api"}

    return app


app = create_app()
