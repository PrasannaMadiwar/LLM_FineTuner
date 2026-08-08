from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.training import (
    TrainingArtifact,
    TrainingCheckpoint,
    TrainingConfig,
    TrainingJob,
    TrainingJobEvent,
    TrainingJobStatus,
    TrainingMetric,
)
from app.infrastructure.models.training import (
    TrainingArtifactModel,
    TrainingCheckpointModel,
    TrainingJobEventModel,
    TrainingJobModel,
    TrainingMetricModel,
)


class TrainingJobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_job(
        self,
        user_id: UUID,
        status: TrainingJobStatus,
        model_key: str,
        model_id: str,
        template_name: str,
        training_config: TrainingConfig,
        dataset_id: str,
        normalized_dataset_path: str,
        project_id: UUID | None = None,
    ) -> TrainingJob:
        now = datetime.now(UTC)
        model = TrainingJobModel(
            user_id=user_id,
            project_id=project_id,
            status=status.value,
            model_key=model_key,
            model_id=model_id,
            template_name=template_name,
            training_config_json=training_config.model_dump(mode="json"),
            dataset_id=dataset_id,
            normalized_dataset_path=normalized_dataset_path,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        await self.add_event(
            training_job_id=model.id,
            user_id=user_id,
            from_status=None,
            to_status=status,
            message="Training job created.",
        )
        return self._to_job(model)

    async def get_job(self, job_id: UUID) -> TrainingJob | None:
        model = await self._session.get(TrainingJobModel, job_id)
        return self._to_job(model) if model else None

    async def list_jobs(self, user_id: UUID) -> list[TrainingJob]:
        result = await self._session.execute(
            select(TrainingJobModel)
            .where(TrainingJobModel.user_id == user_id)
            .order_by(TrainingJobModel.created_at.desc())
        )
        return [self._to_job(model) for model in result.scalars().all()]

    async def update_job(
        self,
        job_id: UUID,
        status: TrainingJobStatus | None = None,
        gpu_instance_id: UUID | None = None,
        error_message: str | None = None,
        queued_at: datetime | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> TrainingJob:
        model = await self._session.get(TrainingJobModel, job_id)
        if model is None:
            raise ValueError("Training job not found.")
        if status is not None:
            model.status = status.value
        if gpu_instance_id is not None:
            model.gpu_instance_id = gpu_instance_id
        if error_message is not None:
            model.error_message = error_message
        if queued_at is not None:
            model.queued_at = queued_at
        if started_at is not None:
            model.started_at = started_at
        if completed_at is not None:
            model.completed_at = completed_at
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_job(model)

    async def add_event(
        self,
        training_job_id: UUID,
        user_id: UUID,
        from_status: TrainingJobStatus | None,
        to_status: TrainingJobStatus,
        message: str,
        metadata: dict | None = None,
    ) -> TrainingJobEvent:
        model = TrainingJobEventModel(
            training_job_id=training_job_id,
            user_id=user_id,
            from_status=from_status.value if from_status else None,
            to_status=to_status.value,
            message=message,
            metadata_json=metadata or {},
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_event(model)

    async def list_events(self, job_id: UUID) -> list[TrainingJobEvent]:
        result = await self._session.execute(
            select(TrainingJobEventModel)
            .where(TrainingJobEventModel.training_job_id == job_id)
            .order_by(TrainingJobEventModel.created_at.asc())
        )
        return [self._to_event(model) for model in result.scalars().all()]

    async def create_metric(self, job_id: UUID, payload: dict) -> TrainingMetric:
        model = TrainingMetricModel(
            training_job_id=job_id,
            epoch=payload.get("epoch") or payload.get("current_epoch"),
            global_step=payload.get("global_step"),
            loss=payload.get("loss"),
            learning_rate=payload.get("learning_rate"),
            tokens_per_second=payload.get("tokens_per_second"),
            samples_per_second=payload.get("samples_per_second") or payload.get("train_samples_per_second"),
            gpu_utilization=payload.get("gpu_utilization"),
            gpu_memory_json=payload.get("gpu_memory") or payload.get("memory") or {},
            cpu_usage=payload.get("cpu_usage"),
            ram_usage_json=payload.get("ram_usage") or {},
            eta_seconds=payload.get("eta_seconds"),
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_metric(model)

    async def list_metrics(self, job_id: UUID) -> list[TrainingMetric]:
        result = await self._session.execute(
            select(TrainingMetricModel)
            .where(TrainingMetricModel.training_job_id == job_id)
            .order_by(TrainingMetricModel.timestamp.asc())
        )
        return [self._to_metric(model) for model in result.scalars().all()]

    async def create_checkpoint(self, job_id: UUID, path: str, metadata: dict | None = None) -> TrainingCheckpoint:
        await self._session.execute(
            TrainingCheckpointModel.__table__.update()
            .where(TrainingCheckpointModel.training_job_id == job_id)
            .values(is_latest=False)
        )
        metadata = metadata or {}
        model = TrainingCheckpointModel(
            training_job_id=job_id,
            epoch=metadata.get("epoch") or metadata.get("current_epoch"),
            global_step=metadata.get("global_step"),
            path=path,
            is_latest=True,
            metadata_json=metadata,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_checkpoint(model)

    async def latest_checkpoint(self, job_id: UUID) -> TrainingCheckpoint | None:
        result = await self._session.execute(
            select(TrainingCheckpointModel)
            .where(TrainingCheckpointModel.training_job_id == job_id, TrainingCheckpointModel.is_latest.is_(True))
            .order_by(TrainingCheckpointModel.created_at.desc())
        )
        model = result.scalar_one_or_none()
        return self._to_checkpoint(model) if model else None

    async def create_artifact(
        self,
        job: TrainingJob,
        artifact_type: str,
        path: str,
        filename: str,
        size_bytes: int,
        checksum: str | None = None,
        metadata: dict | None = None,
    ) -> TrainingArtifact:
        model = TrainingArtifactModel(
            training_job_id=job.id,
            user_id=job.user_id,
            project_id=job.project_id,
            artifact_type=artifact_type,
            path=path,
            filename=filename,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata_json=metadata or {},
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_artifact(model)

    async def list_artifacts(self, job_id: UUID) -> list[TrainingArtifact]:
        result = await self._session.execute(
            select(TrainingArtifactModel)
            .where(TrainingArtifactModel.training_job_id == job_id)
            .order_by(TrainingArtifactModel.created_at.asc())
        )
        return [self._to_artifact(model) for model in result.scalars().all()]

    async def get_artifact(self, artifact_id: UUID) -> TrainingArtifact | None:
        model = await self._session.get(TrainingArtifactModel, artifact_id)
        return self._to_artifact(model) if model else None

    @staticmethod
    def _to_job(model: TrainingJobModel) -> TrainingJob:
        return TrainingJob(
            id=model.id,
            user_id=model.user_id,
            project_id=model.project_id,
            status=TrainingJobStatus(model.status),
            model_key=model.model_key,
            model_id=model.model_id,
            template_name=model.template_name,
            training_config=TrainingConfig(**model.training_config_json),
            dataset_id=model.dataset_id,
            normalized_dataset_path=model.normalized_dataset_path,
            gpu_instance_id=model.gpu_instance_id,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            queued_at=model.queued_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    @staticmethod
    def _to_event(model: TrainingJobEventModel) -> TrainingJobEvent:
        return TrainingJobEvent(
            id=model.id,
            training_job_id=model.training_job_id,
            user_id=model.user_id,
            from_status=TrainingJobStatus(model.from_status) if model.from_status else None,
            to_status=TrainingJobStatus(model.to_status),
            message=model.message,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
        )

    @staticmethod
    def _to_metric(model: TrainingMetricModel) -> TrainingMetric:
        return TrainingMetric(
            id=model.id,
            training_job_id=model.training_job_id,
            timestamp=model.timestamp,
            epoch=model.epoch,
            global_step=model.global_step,
            loss=model.loss,
            learning_rate=model.learning_rate,
            tokens_per_second=model.tokens_per_second,
            samples_per_second=model.samples_per_second,
            gpu_utilization=model.gpu_utilization,
            gpu_memory=model.gpu_memory_json or {},
            cpu_usage=model.cpu_usage,
            ram_usage=model.ram_usage_json or {},
            eta_seconds=model.eta_seconds,
        )

    @staticmethod
    def _to_checkpoint(model: TrainingCheckpointModel) -> TrainingCheckpoint:
        return TrainingCheckpoint(
            id=model.id,
            training_job_id=model.training_job_id,
            epoch=model.epoch,
            global_step=model.global_step,
            path=model.path,
            is_latest=model.is_latest,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
        )

    @staticmethod
    def _to_artifact(model: TrainingArtifactModel) -> TrainingArtifact:
        return TrainingArtifact(
            id=model.id,
            training_job_id=model.training_job_id,
            user_id=model.user_id,
            project_id=model.project_id,
            artifact_type=model.artifact_type,
            path=model.path,
            filename=model.filename,
            size_bytes=model.size_bytes,
            checksum=model.checksum,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
        )
