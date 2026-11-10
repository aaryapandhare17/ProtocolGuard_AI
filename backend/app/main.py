from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.store import Base, configure
from app.api.routes import router
from app.api.fsm import router as fsm_router


def create_app(config=None) -> FastAPI:
    config = config or settings
    engine, factory = configure(config.database_url)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(title="ProtocolGuard AI", version="0.2.0", lifespan=lifespan)
    app.state.settings = config
    app.state.session_factory = factory
    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins.split(","),
        allow_credentials=True, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"])
    app.include_router(router)
    app.include_router(fsm_router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "protocolguard-api"}

    return app


app = create_app()
