from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingJobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    PREPARING = "preparing"
    WAITING_GPU = "waiting_gpu"
    GPU_READY = "gpu_ready"
    UPLOADING = "uploading"
    STARTING = "starting"
    TRAINING = "training"
    CHECKPOINTING = "checkpointing"
    COLLECTING_ARTIFACTS = "collecting_artifacts"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_TRAINING_JOB_STATUSES = {
    TrainingJobStatus.COMPLETED,
    TrainingJobStatus.FAILED,
    TrainingJobStatus.CANCELLED,
}


class ModelDefinition(BaseModel):
    model_key: str
    model_id: str
    display_name: str
    huggingface_repo: str
    template: str
    default_config: dict = Field(default_factory=dict)
    lora_supported: bool = True
    quantization: str = "4bit"
    sequence_length: int = Field(default=2048, ge=1)
    gpu_requirements: dict = Field(default_factory=dict)


class TrainingConfig(BaseModel):
    model_key: str
    dataset_id: str
    normalized_dataset_path: str
    output_dir: str | None = None
    epochs: int = Field(default=3, ge=1, le=100)
    learning_rate: float = Field(default=2e-4, gt=0)
    batch_size: int = Field(default=2, ge=1)
    gradient_accumulation_steps: int = Field(default=4, ge=1)
    lora_rank: int = Field(default=16, ge=1)
    max_sequence_length: int | None = Field(default=None, ge=1)
    load_in_4bit: bool = True
    extra: dict = Field(default_factory=dict)


class TrainingJob(BaseModel):
    id: UUID
    user_id: UUID
    project_id: UUID | None = None
    status: TrainingJobStatus
    model_key: str
    model_id: str
    template_name: str
    training_config: TrainingConfig
    dataset_id: str
    normalized_dataset_path: str
    gpu_instance_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TrainingJobEvent(BaseModel):
    id: UUID
    training_job_id: UUID
    user_id: UUID
    from_status: TrainingJobStatus | None = None
    to_status: TrainingJobStatus
    message: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class TrainingMetric(BaseModel):
    id: UUID
    training_job_id: UUID
    timestamp: datetime
    epoch: float | None = None
    global_step: int | None = None
    loss: float | None = None
    learning_rate: float | None = None
    tokens_per_second: float | None = None
    samples_per_second: float | None = None
    gpu_utilization: float | None = None
    gpu_memory: dict = Field(default_factory=dict)
    cpu_usage: float | None = None
    ram_usage: dict = Field(default_factory=dict)
    eta_seconds: float | None = None


class TrainingCheckpoint(BaseModel):
    id: UUID
    training_job_id: UUID
    epoch: float | None = None
    global_step: int | None = None
    path: str
    is_latest: bool
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class TrainingArtifact(BaseModel):
    id: UUID
    training_job_id: UUID
    user_id: UUID
    project_id: UUID | None = None
    artifact_type: str
    path: str
    filename: str
    size_bytes: int
    checksum: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
