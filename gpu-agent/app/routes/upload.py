from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from app.dependencies import file_service
from app.models.schemas import UploadResponse
from app.services.file_service import FileService

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    remote_path: str,
    file: UploadFile = File(...),
    service: FileService = Depends(file_service),
):
    try:
        path, bytes_uploaded = await service.write_stream(remote_path, _upload_stream(file))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    return UploadResponse(path=str(path), bytes_uploaded=bytes_uploaded)


@router.put("/files", response_model=UploadResponse)
async def upload_raw_file(
    request: Request,
    path: str,
    x_filename: str | None = Header(default=None),
    service: FileService = Depends(file_service),
):
    del x_filename
    try:
        destination, bytes_uploaded = await service.write_stream(path, request.stream())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UploadResponse(path=str(destination), bytes_uploaded=bytes_uploaded)


async def _upload_stream(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(1024 * 1024):
        yield chunk
