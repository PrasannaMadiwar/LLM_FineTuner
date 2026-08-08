from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import log_service
from app.models.schemas import LogEntry
from app.services.log_service import LogService

router = APIRouter()


@router.get("/logs/{training_id}", response_model=list[LogEntry])
async def training_logs(
    training_id: str,
    limit: int = 500,
    service: LogService = Depends(log_service),
):
    return service.read_entries(training_id, limit)


@router.get("/logs")
async def logs(service: LogService = Depends(log_service)):
    return StreamingResponse(service.stream_entries(), media_type="application/x-ndjson")
