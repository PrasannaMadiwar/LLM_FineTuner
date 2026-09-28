from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class GPUProviderName(StrEnum):
    RUNPOD = "runpod"
    LOCAL = "local"


class GPUInstanceStatus(StrEnum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class GPUEventType(StrEnum):
    INSTANCE_CREATE_REQUESTED = "instance_create_requested"
    INSTANCE_CREATED = "instance_created"
    INSTANCE_READY = "instance_ready"
    INSTANCE_TERMINATE_REQUESTED = "instance_terminate_requested"
    INSTANCE_TERMINATED = "instance_terminated"
    INSTANCE_HEALTH_CHECKED = "instance_health_checked"
    FILE_UPLOAD_STARTED = "file_upload_started"
    FILE_UPLOAD_COMPLETED = "file_upload_completed"
    COMMAND_STARTED = "command_started"
    COMMAND_COMPLETED = "command_completed"
    LOGS_REQUESTED = "logs_requested"
    RETRY = "retry"
    ERROR = "error"


class GPUErrorCode(StrEnum):
    MISSING_API_KEY = "missing_api_key"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    GPU_UNAVAILABLE = "gpu_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"
    NETWORK_ERROR = "network_error"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"


class GPUProviderError(BaseModel):
    code: GPUErrorCode
    message: str
    retryable: bool = False
    status_code: int | None = None


class GPUCreateConfig(BaseModel):
    name: str = "llm-fine-tuner-gpu"
    gpu_type: str | None = None
    image: str | None = None
    volume_size_gb: int | None = Field(default=None, ge=1)
    container_disk_gb: int | None = Field(default=None, ge=1)
    region: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class GPUProviderInstance(BaseModel):
    provider_instance_id: str
    status: GPUInstanceStatus
    endpoint_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class GPUStatusResult(BaseModel):
    provider_instance_id: str
    status: GPUInstanceStatus
    message: str | None = None
    endpoint_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class GPUHealthResult(BaseModel):
    healthy: bool
    status: GPUInstanceStatus
    message: str | None = None
    details: dict = Field(default_factory=dict)


class GPUCommand(BaseModel):
    command: str = Field(min_length=1, max_length=4096)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    working_directory: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class GPUCommandResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float


class GPUUploadResult(BaseModel):
    files: list[str]
    bytes_uploaded: int
    duration_seconds: float


class GPUDownloadResult(BaseModel):
    remote_path: str
    bytes_downloaded: int


class GPULogEntry(BaseModel):
    stream: str = "stdout"
    message: str
    timestamp: datetime | None = None


class GPUInstance(BaseModel):
    id: UUID
    provider: GPUProviderName
    provider_instance_id: str | None = None
    status: GPUInstanceStatus
    user_id: UUID
    project_id: UUID | None = None
    gpu_type: str | None = None
    endpoint_url: str | None = None
    cost_estimate: float | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    terminated_at: datetime | None = None


class TrainingSession(BaseModel):
    id: UUID
    gpu_instance_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class GPUEvent(BaseModel):
    id: UUID
    gpu_instance_id: UUID | None = None
    user_id: UUID
    event_type: GPUEventType
    message: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


@dataclass(frozen=True)
class GPUUploadFile:
    filename: str
    remote_path: str
    stream: AsyncIterator[bytes]
    content_type: str | None = None
    size_bytes: int | None = None
