from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.dependencies import (
    ensure_agent_token_configured,
    require_agent_token,
    settings,
    workspace_service,
)
from app.routes import download, health, logs, system, training, upload


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    ensure_agent_token_configured(settings())
    workspace_service().ensure_workspace()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLM Fine-Tuner GPU Runtime Agent",
        version="0.1.0",
        description="Runtime control agent for GPU training pods.",
        lifespan=lifespan,
    )
    protected = [Depends(require_agent_token)]
    app.include_router(health.router, dependencies=protected)
    app.include_router(upload.router, dependencies=protected)
    app.include_router(download.router, dependencies=protected)
    app.include_router(logs.router, dependencies=protected)
    app.include_router(system.router, dependencies=protected)
    app.include_router(training.router, dependencies=protected)

    return app


app = create_app()
