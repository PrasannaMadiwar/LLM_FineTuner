from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import get_current_user, get_gpu_service
from app.domain.gpu import GPUCommand, GPUCreateConfig, GPUUploadFile
from app.infrastructure.gpu.base import GPUProviderException
from app.schemas.gpu import (
    GPUCreateRequest,
    GPUExecuteRequest,
    GPUExecuteResponse,
    GPUHealthResponse,
    GPUInstanceResponse,
    GPUListResponse,
    GPULogsResponse,
    GPUUploadResponse,
)
from app.services.gpu_service import GPUService

router = APIRouter()


@router.post("/create", response_model=GPUInstanceResponse, summary="Create a GPU instance")
async def create_gpu(
    payload: GPUCreateRequest,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        instance = await gpu_service.create_instance(
            user_id=current_user.id,
            project_id=payload.project_id,
            config=GPUCreateConfig(
                name=payload.name,
                gpu_type=payload.gpu_type,
                image=payload.image,
                volume_size_gb=payload.volume_size_gb,
                container_disk_gb=payload.container_disk_gb,
                region=payload.region,
                env=payload.env,
                ports=payload.ports,
                metadata=payload.metadata,
            ),
        )
    except GPUProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    return GPUInstanceResponse(instance=instance)


@router.post("/{instance_id}/terminate", response_model=GPUInstanceResponse, summary="Terminate a GPU")
async def terminate_gpu(
    instance_id: UUID,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        instance = await gpu_service.terminate_instance(current_user.id, instance_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GPUProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    return GPUInstanceResponse(instance=instance)


@router.get("/{instance_id}", response_model=GPUInstanceResponse, summary="Get GPU status")
async def get_gpu(
    instance_id: UUID,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        instance = await gpu_service.get_instance(current_user.id, instance_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GPUInstanceResponse(instance=instance)


@router.get("", response_model=GPUListResponse, summary="List GPU instances")
async def list_gpus(
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    return GPUListResponse(instances=await gpu_service.list_instances(current_user.id))


@router.post("/{instance_id}/execute", response_model=GPUExecuteResponse, summary="Execute a command")
async def execute_command(
    instance_id: UUID,
    payload: GPUExecuteRequest,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        result = await gpu_service.execute_command(
            current_user.id,
            instance_id,
            GPUCommand(
                command=payload.command,
                timeout_seconds=payload.timeout_seconds,
                working_directory=payload.working_directory,
                env=payload.env,
            ),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except GPUProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    return GPUExecuteResponse(result=result)


@router.post("/{instance_id}/upload", response_model=GPUUploadResponse, summary="Upload files to a GPU")
async def upload_file(
    instance_id: UUID,
    remote_path: str = Form(...),
    file: UploadFile = File(...),
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        result = await gpu_service.upload_files(
            current_user.id,
            instance_id,
            [
                GPUUploadFile(
                    filename=file.filename or "upload.bin",
                    remote_path=remote_path,
                    stream=_iter_upload_file(file),
                    content_type=file.content_type,
                )
            ],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except GPUProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    finally:
        await file.close()
    return GPUUploadResponse(result=result)


@router.get("/{instance_id}/logs", response_model=GPULogsResponse, summary="Read GPU logs")
async def get_logs(
    instance_id: UUID,
    limit: int = 500,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        entries = []
        async for entry in gpu_service.stream_logs(current_user.id, instance_id):
            entries.append(entry)
            if len(entries) >= limit:
                break
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GPUProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    return GPULogsResponse(entries=entries)


@router.get("/{instance_id}/health", response_model=GPUHealthResponse, summary="Check GPU health")
async def health_check(
    instance_id: UUID,
    gpu_service: GPUService = Depends(get_gpu_service),
    current_user=Depends(get_current_user),
):
    try:
        health = await gpu_service.health_check(current_user.id, instance_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return GPUHealthResponse(health=health)


async def _iter_upload_file(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(1024 * 1024):
        yield chunk
