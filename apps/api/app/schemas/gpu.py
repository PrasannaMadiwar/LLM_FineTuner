from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.gpu import (
    GPUCommandResult,
    GPUHealthResult,
    GPUInstance,
    GPUInstanceStatus,
    GPULogEntry,
    GPUUploadResult,
)


class GPUCreateRequest(BaseModel):
    name: str = "llm-fine-tuner-gpu"
    project_id: UUID | None = None
    gpu_type: str | None = None
    image: str | None = None
    volume_size_gb: int | None = Field(default=None, ge=1)
    container_disk_gb: int | None = Field(default=None, ge=1)
    region: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    ports: list[int] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class GPUInstanceResponse(BaseModel):
    instance: GPUInstance


class GPUListResponse(BaseModel):
    instances: list[GPUInstance]


class GPUExecuteRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4096)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    working_directory: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class GPUExecuteResponse(BaseModel):
    result: GPUCommandResult


class GPUUploadResponse(BaseModel):
    result: GPUUploadResult


class GPULogsResponse(BaseModel):
    entries: list[GPULogEntry]


class GPUHealthResponse(BaseModel):
    health: GPUHealthResult


class GPUStatusResponse(BaseModel):
    status: GPUInstanceStatus
