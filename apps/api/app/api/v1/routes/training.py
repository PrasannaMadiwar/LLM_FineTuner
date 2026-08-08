from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_training_service
from app.domain.users import User
from app.schemas.training import (
    ModelListResponse,
    TemplateListResponse,
    TrainingArtifactListResponse,
    TrainingArtifactResponse,
    TrainingCheckpointResponse,
    TrainingJobCreateRequest,
    TrainingJobEventListResponse,
    TrainingJobListResponse,
    TrainingJobResponse,
    TrainingJobResumeRequest,
    TrainingMetricListResponse,
)
from app.services.training_service import TrainingService

router = APIRouter()
TrainingServiceDep = Annotated[TrainingService, Depends(get_training_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/models", response_model=ModelListResponse, summary="List supported training models")
async def list_models(
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    return ModelListResponse(models=training_service.list_supported_models())


@router.get("/templates", response_model=TemplateListResponse, summary="List installed templates")
async def list_templates(
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    return TemplateListResponse(templates=training_service.list_templates())


@router.post(
    "/jobs",
    response_model=TrainingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a training job",
)
async def create_training_job(
    payload: TrainingJobCreateRequest,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        job = await training_service.create_job(
            user_id=current_user.id,
            project_id=payload.project_id,
            training_config=payload.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return TrainingJobResponse(job=job)


@router.get("/jobs", response_model=TrainingJobListResponse, summary="List training jobs")
async def list_training_jobs(
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    return TrainingJobListResponse(jobs=await training_service.list_jobs(current_user.id))


@router.get("/jobs/{job_id}", response_model=TrainingJobResponse, summary="Get a training job")
async def get_training_job(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingJobResponse(job=await training_service.get_job(current_user.id, job_id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/queue", response_model=TrainingJobResponse, summary="Queue a training job")
async def queue_training_job(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingJobResponse(job=await training_service.queue_job(current_user.id, job_id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=TrainingJobResponse, summary="Cancel a training job")
async def cancel_training_job(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingJobResponse(job=await training_service.cancel_job(current_user.id, job_id))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/resume", response_model=TrainingJobResponse, summary="Resume a training job")
async def resume_training_job(
    job_id: UUID,
    payload: TrainingJobResumeRequest,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingJobResponse(
            job=await training_service.resume_job(
                current_user.id,
                job_id,
                resume_from_checkpoint=payload.resume_from_checkpoint,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get(
    "/jobs/{job_id}/events",
    response_model=TrainingJobEventListResponse,
    summary="List training job events",
)
async def list_training_job_events(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        events = await training_service.list_events(current_user.id, job_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TrainingJobEventListResponse(events=events)


@router.get("/jobs/{job_id}/metrics", response_model=TrainingMetricListResponse)
async def list_training_metrics(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingMetricListResponse(metrics=await training_service.list_metrics(current_user.id, job_id))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/checkpoints/latest", response_model=TrainingCheckpointResponse)
async def latest_training_checkpoint(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingCheckpointResponse(checkpoint=await training_service.latest_checkpoint(current_user.id, job_id))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/artifacts", response_model=TrainingArtifactListResponse)
async def list_training_artifacts(
    job_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingArtifactListResponse(artifacts=await training_service.list_artifacts(current_user.id, job_id))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/artifacts/{artifact_id}", response_model=TrainingArtifactResponse)
async def get_training_artifact(
    job_id: UUID,
    artifact_id: UUID,
    training_service: TrainingServiceDep,
    current_user: CurrentUserDep,
):
    try:
        return TrainingArtifactResponse(
            artifact=await training_service.get_artifact(current_user.id, job_id, artifact_id)
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
