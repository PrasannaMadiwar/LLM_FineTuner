from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user, get_dataset_service
from app.domain.datasets import DatasetSource
from app.domain.users import User
from app.infrastructure.datasets.base import DatasetNotFoundError, DatasetProviderError
from app.infrastructure.llm.base import LLMProviderException
from app.schemas.datasets import (
    DatasetAnalyzeRequest,
    DatasetAnalyzeResponse,
    DatasetInfoResponse,
    DatasetNormalizeRequest,
    DatasetNormalizeResponse,
    DatasetPreviewResponse,
    DatasetSearchResponse,
)
from app.services.dataset_service import DatasetService

router = APIRouter()
DatasetServiceDep = Annotated[DatasetService, Depends(get_dataset_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SearchQuery = Annotated[str, Query(min_length=1)]


@router.get("/search", response_model=DatasetSearchResponse, summary="Search datasets")
async def search_datasets(
    query: SearchQuery,
    dataset_service: DatasetServiceDep,
    source: DatasetSource | None = None,
):
    return DatasetSearchResponse(results=await dataset_service.search_datasets(query, source))


@router.get("/info/{dataset_id:path}", response_model=DatasetInfoResponse, summary="Get dataset metadata")
async def get_dataset_info(
    dataset_id: str,
    dataset_service: DatasetServiceDep,
    source: DatasetSource = DatasetSource.HUGGING_FACE,
):
    _validate_dataset_id(dataset_id)
    try:
        return DatasetInfoResponse(metadata=await dataset_service.get_dataset_info(dataset_id, source))
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc


@router.get(
    "/preview/{dataset_id:path}",
    response_model=DatasetPreviewResponse,
    summary="Preview dataset rows",
)
async def preview_dataset(
    dataset_id: str,
    dataset_service: DatasetServiceDep,
    source: DatasetSource = DatasetSource.HUGGING_FACE,
    split: str | None = None,
):
    _validate_dataset_id(dataset_id)
    try:
        rows = await dataset_service.preview_dataset(dataset_id, source, split)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    return DatasetPreviewResponse(dataset_id=dataset_id, source=source, split=split, rows=rows)


def _validate_dataset_id(dataset_id: str) -> None:
    if not dataset_id.strip() or ".." in dataset_id or dataset_id.startswith("/") or dataset_id.endswith("/"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Malformed dataset id.")


@router.post("/analyze", response_model=DatasetAnalyzeResponse, summary="Analyze dataset semantics")
async def analyze_dataset(
    payload: DatasetAnalyzeRequest,
    dataset_service: DatasetServiceDep,
):
    try:
        mapping = await dataset_service.analyze_dataset(payload.dataset_id, payload.source)
    except LLMProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DatasetAnalyzeResponse(dataset_id=payload.dataset_id, mapping=mapping)


@router.post("/normalize", response_model=DatasetNormalizeResponse, summary="Normalize dataset samples")
async def normalize_dataset(
    payload: DatasetNormalizeRequest,
    dataset_service: DatasetServiceDep,
    current_user: CurrentUserDep,
):
    try:
        normalized_rows, validation_report, artifact_path = await dataset_service.normalize_dataset(
            dataset_id=payload.dataset_id,
            source=payload.source,
            mapping=payload.mapping,
            rows=payload.rows,
            split=payload.split,
            user_id=current_user.id,
            project_id=payload.project_id,
        )
    except LLMProviderException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.error.model_dump(mode="json"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DatasetNormalizeResponse(
        dataset_id=payload.dataset_id,
        normalized_rows=normalized_rows,
        validation_report=validation_report,
        artifact_path=artifact_path,
    )
