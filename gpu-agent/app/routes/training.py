from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import training_service
from app.models.schemas import (
    TrainingRequest,
    TrainingStartResponse,
    TrainingStatusResponse,
)
from app.services.training_service import TrainingService

router = APIRouter()


@router.post("/train", response_model=TrainingStartResponse)
async def train(
    payload: TrainingRequest,
    service: TrainingService = Depends(training_service),
):
    try:
        record = await service.start_training(payload)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TrainingStartResponse(training_id=record.training_id, state=record.state)


@router.post("/cancel/{training_id}", response_model=TrainingStatusResponse)
async def cancel(training_id: str, service: TrainingService = Depends(training_service)):
    try:
        record = await service.cancel_training(training_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.status(record.training_id)


@router.get("/status/{training_id}", response_model=TrainingStatusResponse)
async def status(training_id: str, service: TrainingService = Depends(training_service)):
    try:
        return service.status(training_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
