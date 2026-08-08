from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.dependencies import file_service
from app.models.schemas import ArtifactItem, ArtifactListResponse, DownloadMetadataResponse
from app.services.file_service import FileService

router = APIRouter()


@router.get("/artifacts/{training_id}", response_model=ArtifactListResponse)
async def artifacts(training_id: str, service: FileService = Depends(file_service)):
    items = [
        ArtifactItem(
            path=item["path"],
            size_bytes=item["size_bytes"],
            modified_at=datetime.fromtimestamp(item["modified_at"], UTC),
        )
        for item in service.list_artifacts(training_id)
    ]
    return ArtifactListResponse(training_id=training_id, artifacts=items)


@router.post("/download/{training_id}")
async def download_artifact(
    training_id: str,
    path: str,
    service: FileService = Depends(file_service),
):
    del training_id
    try:
        file_path, _ = service.file_metadata(path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(file_path)


@router.get("/files", response_model=DownloadMetadataResponse)
async def file_metadata(path: str, service: FileService = Depends(file_service)):
    try:
        _, bytes_downloaded = service.file_metadata(path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DownloadMetadataResponse(remote_path=path, bytes_downloaded=bytes_downloaded)
