from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import training_service, workspace_service
from app.models.schemas import CleanupResponse, CommandRequest, CommandResponse
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.post("/commands", response_model=CommandResponse)
async def execute_command(
    payload: CommandRequest,
    service: TrainingService = Depends(training_service),
):
    try:
        return await service.execute_command(payload)
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup(service: WorkspaceService = Depends(workspace_service)):
    deleted_paths, bytes_deleted = service.cleanup_temp()
    return CleanupResponse(deleted_paths=deleted_paths, bytes_deleted=bytes_deleted)
