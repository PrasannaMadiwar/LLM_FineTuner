from uuid import UUID

from pydantic import BaseModel

from app.domain.training import (
    ModelDefinition,
    TrainingArtifact,
    TrainingCheckpoint,
    TrainingConfig,
    TrainingJob,
    TrainingJobEvent,
    TrainingMetric,
)


class ModelListResponse(BaseModel):
    models: list[ModelDefinition]


class TemplateListResponse(BaseModel):
    templates: list[str]


class TrainingJobCreateRequest(BaseModel):
    project_id: UUID | None = None
    config: TrainingConfig


class TrainingJobResumeRequest(BaseModel):
    resume_from_checkpoint: str | None = None


class TrainingJobResponse(BaseModel):
    job: TrainingJob


class TrainingJobListResponse(BaseModel):
    jobs: list[TrainingJob]


class TrainingJobEventListResponse(BaseModel):
    events: list[TrainingJobEvent]


class TrainingMetricListResponse(BaseModel):
    metrics: list[TrainingMetric]


class TrainingCheckpointResponse(BaseModel):
    checkpoint: TrainingCheckpoint | None = None


class TrainingArtifactResponse(BaseModel):
    artifact: TrainingArtifact


class TrainingArtifactListResponse(BaseModel):
    artifacts: list[TrainingArtifact]
