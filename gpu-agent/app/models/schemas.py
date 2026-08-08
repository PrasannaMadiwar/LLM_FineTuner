from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class TrainingState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class HealthResponse(BaseModel):
    status: str
    gpu_status: str
    disk: dict
    ram: dict
    vram: dict | None = None
    cuda_version: str | None = None
    torch_version: str | None = None
    installed_models: list[str] = Field(default_factory=list)
    workspace_size_bytes: int
    container_uptime_seconds: float


class UploadResponse(BaseModel):
    path: str
    bytes_uploaded: int


class DownloadMetadataResponse(BaseModel):
    remote_path: str
    bytes_downloaded: int


class TrainingRequest(BaseModel):
    template: str = Field(min_length=1)
    dataset_path: str
    config: dict = Field(default_factory=dict)
    model: str | None = None
    output_dir: str | None = None
    resume_from_checkpoint: str | None = None


class TrainingStartResponse(BaseModel):
    training_id: str
    state: TrainingState


class TrainingStatusResponse(BaseModel):
    training_id: str
    state: TrainingState
    current_epoch: int | None = None
    loss: float | None = None
    learning_rate: float | None = None
    eta_seconds: float | None = None
    global_step: int | None = None
    metrics: dict = Field(default_factory=dict)
    checkpoints: list[str] = Field(default_factory=list)
    gpu_utilization: float | None = None
    memory: dict = Field(default_factory=dict)
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class ArtifactItem(BaseModel):
    path: str
    size_bytes: int
    modified_at: datetime


class ArtifactListResponse(BaseModel):
    training_id: str
    artifacts: list[ArtifactItem]


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4096)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    working_directory: str | None = None
    env: dict[str, str] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float


class LogEntry(BaseModel):
    stream: str = "stdout"
    message: str
    timestamp: datetime | None = None


class CleanupResponse(BaseModel):
    deleted_paths: list[str]
    bytes_deleted: int


class TrainingRecord(BaseModel):
    training_id: str
    template: str
    state: TrainingState
    config_path: Path
    dataset_path: Path
    output_dir: Path
    artifact_dir: Path
    log_stdout_path: Path
    log_stderr_path: Path
    process_id: int | None = None
    current_epoch: int | None = None
    loss: float | None = None
    learning_rate: float | None = None
    eta_seconds: float | None = None
    global_step: int | None = None
    metrics: dict = Field(default_factory=dict)
    checkpoints: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
