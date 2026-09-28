from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetSource(StrEnum):
    HUGGING_FACE = "hugging_face"
    KAGGLE = "kaggle"
    GITHUB = "github"
    DEMO = "demo"


class DatasetSearchResult(BaseModel):
    dataset_id: str
    name: str
    source: DatasetSource
    description: str | None = None
    license: str | None = None
    size: int | None = None
    downloads: int | None = None
    likes: int | None = None


class DatasetMetadata(BaseModel):
    dataset_id: str
    name: str
    source: DatasetSource
    description: str | None = None
    license: str | None = None
    size: int | None = None
    features: dict = Field(default_factory=dict)
    column_names: list[str] = Field(default_factory=list)
    splits: list[str] = Field(default_factory=list)
    row_counts: dict[str, int] = Field(default_factory=dict)
    sample_rows: list[dict] = Field(default_factory=list)


class SemanticMapping(BaseModel):
    user: list[str]
    assistant: str
    system: str | None = None
    context: list[str] = Field(default_factory=list)


class MappingResult(SemanticMapping):
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class MappingRecord(BaseModel):
    id: UUID
    dataset_name: str
    mapping_json: MappingResult
    confidence: float
    created_at: datetime
    updated_at: datetime


class LLMErrorCode(StrEnum):
    MISSING_API_KEY = "missing_api_key"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    INVALID_RESPONSE = "invalid_response"


class LLMProviderError(BaseModel):
    code: LLMErrorCode
    message: str
    retryable: bool = False
    status_code: int | None = None


class NormalizedMessage(BaseModel):
    role: str
    content: str


class NormalizedConversation(BaseModel):
    messages: list[NormalizedMessage]


class ValidationIssue(BaseModel):
    code: str
    message: str
    row_index: int | None = None
    severity: str = "error"


class ValidationReport(BaseModel):
    is_valid: bool
    total_rows: int
    valid_rows: int
    issues: list[ValidationIssue] = Field(default_factory=list)


class DatasetNormalizationArtifact(BaseModel):
    dataset_id: str
    dataset_name: str
    source: DatasetSource
    split: str | None = None
    path: str
    row_count: int
    validation_report: ValidationReport
