from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.domain.training import TrainingConfig, TrainingJob, TrainingJobEvent, TrainingJobStatus
from app.infrastructure.repositories.training_job_repository import TrainingJobRepository
from app.services.model_registry import ModelRegistry
from app.services.template_loader import TemplateLoader
from app.services.training_state_machine import TrainingStateMachine
from app.services.training_task_dispatcher import TrainingTaskDispatcher


class TrainingService:
    def __init__(
        self,
        repository: TrainingJobRepository,
        model_registry: ModelRegistry,
        template_loader: TemplateLoader,
        state_machine: TrainingStateMachine,
        task_dispatcher: TrainingTaskDispatcher | None = None,
    ):
        self._repository = repository
        self._model_registry = model_registry
        self._template_loader = template_loader
        self._state_machine = state_machine
        self._task_dispatcher = task_dispatcher

    def list_supported_models(self):
        return self._model_registry.list_models()

    def list_templates(self) -> list[str]:
        return self._template_loader.list_templates()

    async def create_job(
        self,
        user_id: UUID,
        training_config: TrainingConfig,
        project_id: UUID | None = None,
    ) -> TrainingJob:
        model = self._model_registry.get_model(training_config.model_key)
        template_name = self._template_loader.resolve_template(model.template)
        self._require_normalized_dataset(training_config.normalized_dataset_path)
        resolved_config = self._apply_model_defaults(training_config, model.sequence_length)
        return await self._repository.create_job(
            user_id=user_id,
            project_id=project_id,
            status=TrainingJobStatus.CREATED,
            model_key=model.model_key,
            model_id=model.model_id,
            template_name=template_name,
            training_config=resolved_config,
            dataset_id=resolved_config.dataset_id,
            normalized_dataset_path=resolved_config.normalized_dataset_path,
        )

    async def queue_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        job = await self._require_owned_job(user_id, job_id)
        queued = await self.transition_job(
            user_id=user_id,
            job_id=job.id,
            next_status=TrainingJobStatus.QUEUED,
            message="Training job queued.",
            queued_at=datetime.now(UTC),
        )
        if self._task_dispatcher is not None:
            task_id = self._task_dispatcher.dispatch(user_id, job.id)
            await self._repository.add_event(
                training_job_id=job.id,
                user_id=user_id,
                from_status=TrainingJobStatus.QUEUED,
                to_status=TrainingJobStatus.QUEUED,
                message="Training worker task dispatched.",
                metadata={"celery_task_id": task_id},
            )
        return queued

    async def get_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        return await self._require_owned_job(user_id, job_id)

    async def list_jobs(self, user_id: UUID) -> list[TrainingJob]:
        return await self._repository.list_jobs(user_id)

    async def list_events(self, user_id: UUID, job_id: UUID) -> list[TrainingJobEvent]:
        await self._require_owned_job(user_id, job_id)
        return await self._repository.list_events(job_id)

    async def record_event(
        self,
        user_id: UUID,
        job_id: UUID,
        message: str,
        metadata: dict | None = None,
    ) -> TrainingJobEvent:
        job = await self._require_owned_job(user_id, job_id)
        return await self._repository.add_event(
            training_job_id=job.id,
            user_id=user_id,
            from_status=job.status,
            to_status=job.status,
            message=message,
            metadata=metadata,
        )

    async def record_runtime_metrics(self, user_id: UUID, job_id: UUID, payload: dict) -> None:
        await self._require_owned_job(user_id, job_id)
        await self._repository.create_metric(job_id, payload)

    async def record_checkpoint(self, user_id: UUID, job_id: UUID, path: str, metadata: dict | None = None) -> None:
        await self._require_owned_job(user_id, job_id)
        await self._repository.create_checkpoint(job_id, path, metadata)

    async def record_artifact(
        self,
        user_id: UUID,
        job_id: UUID,
        artifact_type: str,
        path: str,
        filename: str,
        size_bytes: int,
        checksum: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        job = await self._require_owned_job(user_id, job_id)
        await self._repository.create_artifact(
            job=job,
            artifact_type=artifact_type,
            path=path,
            filename=filename,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata=metadata,
        )

    async def list_artifacts(self, user_id: UUID, job_id: UUID):
        await self._require_owned_job(user_id, job_id)
        return await self._repository.list_artifacts(job_id)

    async def get_artifact(self, user_id: UUID, job_id: UUID, artifact_id: UUID):
        await self._require_owned_job(user_id, job_id)
        artifact = await self._repository.get_artifact(artifact_id)
        if artifact is None or artifact.training_job_id != job_id or artifact.user_id != user_id:
            raise ValueError("Training artifact not found.")
        return artifact

    async def list_metrics(self, user_id: UUID, job_id: UUID):
        await self._require_owned_job(user_id, job_id)
        return await self._repository.list_metrics(job_id)

    async def latest_checkpoint(self, user_id: UUID, job_id: UUID):
        await self._require_owned_job(user_id, job_id)
        return await self._repository.latest_checkpoint(job_id)

    async def transition_job(
        self,
        user_id: UUID,
        job_id: UUID,
        next_status: TrainingJobStatus,
        message: str,
        metadata: dict | None = None,
        gpu_instance_id: UUID | None = None,
        error_message: str | None = None,
        queued_at: datetime | None = None,
    ) -> TrainingJob:
        job = await self._require_owned_job(user_id, job_id)
        self._state_machine.validate_transition(job.status, next_status)
        now = datetime.now(UTC)
        updated = await self._repository.update_job(
            job_id,
            status=next_status,
            gpu_instance_id=gpu_instance_id,
            error_message=error_message,
            queued_at=queued_at,
            started_at=now if next_status == TrainingJobStatus.TRAINING else None,
            completed_at=now if next_status in {TrainingJobStatus.COMPLETED, TrainingJobStatus.FAILED} else None,
        )
        await self._repository.add_event(
            training_job_id=job_id,
            user_id=user_id,
            from_status=job.status,
            to_status=next_status,
            message=message,
            metadata=metadata,
        )
        return updated

    async def cancel_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        return await self.transition_job(
            user_id=user_id,
            job_id=job_id,
            next_status=TrainingJobStatus.CANCELLED,
            message="Training job cancelled.",
        )

    async def resume_job(
        self,
        user_id: UUID,
        job_id: UUID,
        resume_from_checkpoint: str | None = None,
    ) -> TrainingJob:
        source = await self._require_owned_job(user_id, job_id)
        if source.status not in {
            TrainingJobStatus.FAILED,
            TrainingJobStatus.CANCELLED,
            TrainingJobStatus.COMPLETED,
        }:
            raise ValueError("Only terminal training jobs can be resumed.")
        latest = await self._repository.latest_checkpoint(job_id)
        checkpoint = resume_from_checkpoint or (latest.path if latest else source.training_config.extra.get("resume_from_checkpoint"))
        if not checkpoint:
            raise ValueError("A checkpoint path is required to resume training.")
        config = source.training_config.model_copy(
            update={
                "extra": {
                    **source.training_config.extra,
                    "resume_from_checkpoint": checkpoint,
                    "resumed_from_job_id": str(source.id),
                }
            }
        )
        resumed = await self.create_job(user_id=user_id, project_id=source.project_id, training_config=config)
        await self.record_event(
            user_id=user_id,
            job_id=resumed.id,
            message="Training job created from resume checkpoint.",
            metadata={"source_job_id": str(source.id), "resume_from_checkpoint": checkpoint},
        )
        return resumed

    async def _require_owned_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        job = await self._repository.get_job(job_id)
        if job is None:
            raise ValueError("Training job not found.")
        if job.user_id != user_id:
            raise PermissionError("You do not have access to this training job.")
        return job

    @staticmethod
    def _require_normalized_dataset(normalized_dataset_path: str) -> None:
        # Reject bad paths when the job is created, not minutes later in the worker,
        # and only accept files the platform wrote into its own storage.
        storage_root = Path(get_settings().storage_path).resolve()
        dataset_path = Path(normalized_dataset_path).resolve()
        if storage_root not in dataset_path.parents:
            raise ValueError("The training dataset must be a dataset normalized by this platform.")
        if not dataset_path.is_file():
            raise ValueError("The normalized dataset file does not exist. Normalize the dataset before training.")

    @staticmethod
    def _apply_model_defaults(config: TrainingConfig, sequence_length: int) -> TrainingConfig:
        if config.max_sequence_length is not None:
            return config
        return config.model_copy(update={"max_sequence_length": sequence_length})
