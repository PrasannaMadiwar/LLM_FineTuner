import asyncio
from pathlib import Path
from uuid import UUID

from app.domain.gpu import GPUCreateConfig
from app.domain.training import TrainingJob, TrainingJobStatus
from app.infrastructure.gpu.base import GPUProviderException
from app.infrastructure.runtime_agent_client import RuntimeAgentClient, RuntimeAgentError
from app.services.gpu_service import GPUService
from app.services.training_service import TrainingService


class TrainingOrchestrator:
    def __init__(
        self,
        training_service: TrainingService,
        gpu_service: GPUService,
        runtime_client_factory=RuntimeAgentClient,
        poll_interval_seconds: float = 10.0,
        poll_timeout_seconds: int = 86400,
    ):
        self._training_service = training_service
        self._gpu_service = gpu_service
        self._runtime_client_factory = runtime_client_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds

    async def run_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        job = await self._training_service.get_job(user_id, job_id)
        gpu_instance_id: UUID | None = None
        client: RuntimeAgentClient | None = None
        try:
            job = await self._transition(
                job,
                TrainingJobStatus.PREPARING,
                "Training worker started preparing the job.",
            )
            dataset_path = self._require_local_dataset(job.normalized_dataset_path)

            job = await self._transition(
                job,
                TrainingJobStatus.WAITING_GPU,
                "Training worker is creating a GPU instance.",
            )
            gpu = await self._gpu_service.create_instance(
                user_id=user_id,
                project_id=job.project_id,
                config=GPUCreateConfig(
                    name=f"training-{job.id}",
                    gpu_type=job.training_config.extra.get("gpu_type"),
                    image=job.training_config.extra.get("image"),
                    metadata={"training_job_id": str(job.id), "model_key": job.model_key},
                ),
            )
            gpu_instance_id = gpu.id
            if not gpu.endpoint_url:
                raise RuntimeAgentError("GPU agent endpoint is not available.")

            job = await self._transition(
                job,
                TrainingJobStatus.GPU_READY,
                "GPU instance is ready.",
                gpu_instance_id=gpu.id,
                metadata={"endpoint_url": gpu.endpoint_url},
            )
            client = self._runtime_client_factory(gpu.endpoint_url)
            await client.health()

            job = await self._transition(
                job,
                TrainingJobStatus.UPLOADING,
                "Uploading dataset and training configuration to the GPU agent.",
            )
            remote_dataset_path = f"dataset/{job.id}.jsonl"
            remote_config_path = f"configs/{job.id}.json"
            await client.upload_file(dataset_path, remote_dataset_path)
            await client.upload_json(remote_config_path, self._runtime_config(job, remote_dataset_path))

            job = await self._transition(
                job,
                TrainingJobStatus.STARTING,
                "Starting training on the GPU agent.",
            )
            started = await client.start_training(
                template=job.template_name,
                dataset_path=remote_dataset_path,
                config={"config_path": remote_config_path, **job.training_config.model_dump(mode="json")},
            )

            job = await self._transition(
                job,
                TrainingJobStatus.TRAINING,
                "GPU agent accepted the training run.",
                metadata={"runtime_training_id": started.training_id, "runtime_state": started.state},
            )
            status = await self._wait_for_runtime_completion(user_id, job_id, client, started.training_id)
            if status.state != "succeeded":
                raise RuntimeAgentError(status.error or f"Training finished with state '{status.state}'.")

            job = await self._transition(
                job,
                TrainingJobStatus.COLLECTING_ARTIFACTS,
                "Collecting training artifacts from the GPU agent.",
                metadata=status.model_dump(mode="json"),
            )
            artifacts = await client.artifacts(started.training_id)
            for artifact in artifacts.artifacts:
                await self._training_service.record_artifact(
                    user_id=user_id,
                    job_id=job_id,
                    artifact_type=self._artifact_type(artifact.path),
                    path=artifact.path,
                    filename=Path(artifact.path).name,
                    size_bytes=artifact.size_bytes,
                    metadata={"runtime_training_id": started.training_id},
                )
            return await self._transition(
                job,
                TrainingJobStatus.COMPLETED,
                "Training job completed.",
                metadata=artifacts.model_dump(mode="json"),
            )
        except Exception as exc:
            latest = await self._training_service.get_job(user_id, job_id)
            if latest.status == TrainingJobStatus.CANCELLED:
                job = latest
            elif latest.status != TrainingJobStatus.FAILED:
                job = await self._transition(
                    latest,
                    TrainingJobStatus.FAILED,
                    "Training job failed.",
                    error_message=str(exc),
                )
            else:
                job = latest
            raise
        finally:
            if client is not None:
                try:
                    await client.cleanup()
                except RuntimeAgentError as exc:
                    await self._training_service.record_event(
                        user_id=user_id,
                        job_id=job_id,
                        message="Runtime agent cleanup failed.",
                        metadata={"error": str(exc)},
                    )
            if gpu_instance_id is not None:
                try:
                    await self._gpu_service.terminate_instance(user_id, gpu_instance_id)
                    await self._training_service.record_event(
                        user_id=user_id,
                        job_id=job_id,
                        message="GPU instance cleanup completed.",
                        metadata={"gpu_instance_id": str(gpu_instance_id)},
                    )
                except (GPUProviderException, PermissionError, ValueError) as exc:
                    await self._training_service.record_event(
                        user_id=user_id,
                        job_id=job_id,
                        message="GPU instance cleanup failed.",
                        metadata={"gpu_instance_id": str(gpu_instance_id), "error": str(exc)},
                    )

    async def _transition(
        self,
        job: TrainingJob,
        next_status: TrainingJobStatus,
        message: str,
        metadata: dict | None = None,
        gpu_instance_id: UUID | None = None,
        error_message: str | None = None,
    ) -> TrainingJob:
        return await self._training_service.transition_job(
            user_id=job.user_id,
            job_id=job.id,
            next_status=next_status,
            message=message,
            metadata=metadata,
            gpu_instance_id=gpu_instance_id,
            error_message=error_message,
        )

    @staticmethod
    def _require_local_dataset(normalized_dataset_path: str) -> Path:
        path = Path(normalized_dataset_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError("Normalized dataset file does not exist.")
        return path

    @staticmethod
    def _runtime_config(job: TrainingJob, remote_dataset_path: str) -> dict:
        training_config = job.training_config.model_dump(mode="json")
        extra = training_config.pop("extra", {}) or {}
        runtime_training_config = {**training_config, **extra}
        return {
            "training_job_id": str(job.id),
            "model_id": job.model_id,
            "model_key": job.model_key,
            "template": job.template_name,
            "dataset_path": remote_dataset_path,
            "output_dir": job.training_config.output_dir,
            "training_config": runtime_training_config,
        }

    async def _wait_for_runtime_completion(
        self,
        user_id: UUID,
        job_id: UUID,
        client: RuntimeAgentClient,
        runtime_training_id: str,
    ):
        elapsed = 0.0
        checkpoint_snapshot: set[str] = set()
        while elapsed <= self._poll_timeout_seconds:
            latest = await self._training_service.get_job(user_id, job_id)
            if latest.status == TrainingJobStatus.CANCELLED:
                status = await client.cancel(runtime_training_id)
                raise RuntimeAgentError(status.error or "Training job was cancelled.")

            status = await client.status(runtime_training_id)
            checkpoints = set(status.checkpoints)
            if checkpoints - checkpoint_snapshot:
                checkpoint_snapshot = checkpoints
                for checkpoint in checkpoints:
                    await self._training_service.record_checkpoint(
                        user_id=user_id,
                        job_id=job_id,
                        path=checkpoint,
                        metadata=status.model_dump(mode="json"),
                    )
                await self._transition(
                    latest,
                    TrainingJobStatus.CHECKPOINTING,
                    "Runtime training checkpoint detected.",
                    metadata=status.model_dump(mode="json"),
                )
                latest = await self._training_service.get_job(user_id, job_id)
                await self._transition(
                    latest,
                    TrainingJobStatus.TRAINING,
                    "Runtime training continued after checkpoint.",
                    metadata={"checkpoints": sorted(checkpoint_snapshot)},
                )
            elif status.metrics:
                await self._training_service.record_runtime_metrics(user_id, job_id, status.metrics)
                await self._training_service.record_event(
                    user_id=user_id,
                    job_id=job_id,
                    message="Runtime training metrics updated.",
                    metadata=status.model_dump(mode="json"),
                )

            if status.state in {"succeeded", "failed", "cancelled"}:
                return status
            await asyncio.sleep(self._poll_interval_seconds)
            elapsed += self._poll_interval_seconds
        raise RuntimeAgentError("Timed out waiting for GPU agent training to finish.")

    @staticmethod
    def _artifact_type(path: str) -> str:
        lowered = path.lower()
        if "checkpoint" in lowered:
            return "checkpoint"
        if "tokenizer" in lowered:
            return "tokenizer"
        if "adapter" in lowered or lowered.endswith(".safetensors"):
            return "adapter"
        if "metric" in lowered:
            return "metrics"
        if "config" in lowered:
            return "config"
        if "log" in lowered:
            return "logs"
        return "model"
