import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.services.file_service import FileService
from app.services.health_service import HealthService
from app.services.log_service import LogService
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService


@lru_cache
def settings() -> Settings:
    return get_settings()


@lru_cache
def workspace_service() -> WorkspaceService:
    service = WorkspaceService(settings())
    service.ensure_workspace()
    return service


@lru_cache
def file_service() -> FileService:
    return FileService(settings(), workspace_service())


@lru_cache
def log_service() -> LogService:
    return LogService(workspace_service())


@lru_cache
def health_service() -> HealthService:
    return HealthService(settings(), workspace_service())


@lru_cache
def training_service() -> TrainingService:
    return TrainingService(settings(), workspace_service(), file_service(), log_service())


class MissingAgentTokenError(RuntimeError):
    pass


def ensure_agent_token_configured(configured: Settings) -> None:
    if not (configured.agent_token or "").strip():
        raise MissingAgentTokenError(
            "GPU_AGENT_TOKEN is not set. The GPU agent refuses to start without it, "
            "because every endpoint can upload files, run training, or execute commands."
        )


def require_agent_token(
    configured: Annotated[Settings, Depends(settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    token = (configured.agent_token or "").strip()
    if not token:
        # Startup already refuses to run without a token; this keeps requests closed
        # if the app is ever served without going through that startup check.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GPU agent token is not configured.",
        )
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing GPU agent token.")
    if not secrets.compare_digest(authorization.removeprefix(prefix), token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid GPU agent token.")
