from pydantic import BaseModel, Field

from app.domain.datasets import (
    DatasetMetadata,
    DatasetSearchResult,
    DatasetSource,
    MappingResult,
    NormalizedConversation,
    SemanticMapping,
    ValidationReport,
)


class DatasetSearchResponse(BaseModel):
    results: list[DatasetSearchResult]


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    source: DatasetSource
    split: str | None = None
    rows: list[dict]


class DatasetAnalyzeRequest(BaseModel):
    dataset_id: str
    source: DatasetSource = DatasetSource.HUGGING_FACE


class DatasetAnalyzeResponse(BaseModel):
    dataset_id: str
    mapping: MappingResult


class DatasetNormalizeRequest(BaseModel):
    dataset_id: str
    source: DatasetSource = DatasetSource.HUGGING_FACE
    split: str | None = None
    mapping: SemanticMapping | None = None
    rows: list[dict] | None = Field(default=None, description="Optional sample rows to normalize.")


class DatasetNormalizeResponse(BaseModel):
    dataset_id: str
    normalized_rows: list[NormalizedConversation]
    validation_report: ValidationReport


class DatasetInfoResponse(BaseModel):
    metadata: DatasetMetadata
