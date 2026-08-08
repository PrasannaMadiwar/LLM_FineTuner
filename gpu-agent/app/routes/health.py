from fastapi import APIRouter, Depends

from app.dependencies import health_service
from app.models.schemas import HealthResponse
from app.services.health_service import HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(service: HealthService = Depends(health_service)):
    return service.get_health()
