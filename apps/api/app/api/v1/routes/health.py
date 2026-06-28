from fastapi import APIRouter

from app.core.cache import ping_redis
from app.core.database import ping_database

router = APIRouter()


@router.get("/health", summary="Check API health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Check backing service readiness")
async def readiness_check() -> dict[str, str]:
    database_status = "ok" if await ping_database() else "unavailable"
    redis_status = "ok" if await ping_redis() else "unavailable"
    return {"database": database_status, "redis": redis_status}
