import asyncio
from pathlib import Path
from uuid import UUID

from app.domain.gpu import GPUCreateConfig
from app.domain.training import TrainingJob, TrainingJobStatus
from app.infrastructure.runtime_agent_client import RuntimeAgentClient, RuntimeAgentError
from app.services.gpu_service import GPUService
from app.services.training_service import TrainingService


class TrainingJobCancelled(Exception):
    pass


class TrainingOrchestrator:
    def __init__(
        self,
        training_service: TrainingService,
        gpu_service: GPUService,
        runtime_client_factory=RuntimeAgentClient,
        poll_interval_seconds: float = 10.0,
        poll_timeout_seconds: int = 86400,
        max_consecutive_poll_failures: int = 5,
    ):
        self._training_service = training_service
        self._gpu_service = gpu_service
        self._runtime_client_factory = runtime_client_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._max_consecutive_poll_failures = max_consecutive_poll_failures

    async def run_job(self, user_id: UUID, job_id: UUID) -> TrainingJob:
        job = await self._training_service.get_job(user_id, job_id)
        if job.status != TrainingJobStatus.QUEUED:
            # A redelivered or duplicate task must not touch a job another run owns.
            return job
        gpu_instance_id: UUID | None = None
        client: RuntimeAgentClient | None = None
        try:
            await self._raise_if_cancelled(user_id, job_id)
            job = await self._transition(
                job,
                TrainingJobStatus.PREPARING,
                "Training worker started preparing the job.",
            )
            dataset_path = self._require_local_dataset(job.normalized_dataset_path)

            await self._raise_if_cancelled(user_id, job_id)
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

            await self._raise_if_cancelled(user_id, job_id)
            job = await self._transition(
                job,
                TrainingJobStatus.GPU_READY,
                "GPU instance is ready.",
                gpu_instance_id=gpu.id,
                metadata={"endpoint_url": gpu.endpoint_url},
            )
            client = self._runtime_client_factory(gpu.endpoint_url)
            await client.health()

            await self._raise_if_cancelled(user_id, job_id)
            job = await self._transition(
                job,
                TrainingJobStatus.UPLOADING,
                "Uploading dataset and training configuration to the GPU agent.",
            )
            remote_dataset_path = f"dataset/{job.id}.jsonl"
            remote_config_path = f"configs/{job.id}.json"
            await client.upload_file(dataset_path, remote_dataset_path)
            await client.upload_json(remote_config_path, self._runtime_config(job, remote_dataset_path))

            await self._raise_if_cancelled(user_id, job_id)
            job = await self._transition(
                job,
                TrainingJobStatus.STARTING,
                "Starting training on the GPU agent.",
            )
            started = await client.start_training(
                template=job.template_name,
                model=job.model_id,
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
                if status.state == "cancelled":
                    raise TrainingJobCancelled()
                raise RuntimeAgentError(status.error or f"Training finished with state '{status.state}'.")

            if status.checkpoints:
                job = await self._transition(
                    job,
                    TrainingJobStatus.CHECKPOINTING,
                    "Recording checkpoints reported by the GPU agent.",
                )
                for checkpoint_path in status.checkpoints:
                    await self._training_service.record_checkpoint(
                        user_id=user_id,
                        job_id=job_id,
                        path=checkpoint_path,
                        metadata={"runtime_training_id": started.training_id},
                    )

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
            )

        except TrainingJobCancelled:
            await self._training_service.record_event(
                user_id=user_id,
                job_id=job_id,
                message="Training worker stopped after cancellation.",
            )
            return await self._training_service.get_job(user_id, job_id)
        except Exception as exc:
            current_job = await self._training_service.get_job(user_id, job_id)
            if current_job.status != TrainingJobStatus.CANCELLED:
                await self._transition(
                    current_job,
                    TrainingJobStatus.FAILED,
                    "Training job failed.",
                    error_message=str(exc),
                )
            raise
        finally:
            if client is not None:
                await self._cleanup_runtime(client, user_id, job_id)
            if gpu_instance_id is not None:
                await self._terminate_gpu(gpu_instance_id, user_id, job_id)

    async def _wait_for_runtime_completion(
        self,
        user_id: UUID,
        job_id: UUID,
        client: RuntimeAgentClient,
        training_id: str,
    ):
        deadline = asyncio.get_running_loop().time() + self._poll_timeout_seconds
        consecutive_failures = 0
        while asyncio.get_running_loop().time() < deadline:
            if await self._is_cancelled(user_id, job_id):
                await client.cancel(training_id)
                raise TrainingJobCancelled()

            try:
                status = await client.status(training_id)
            except RuntimeAgentError:
                # One dropped request must not fail a run that is still training.
                consecutive_failures += 1
                if consecutive_failures >= self._max_consecutive_poll_failures:
                    raise
                await asyncio.sleep(self._poll_interval_seconds)
                continue
            consecutive_failures = 0
            if status.state in {"succeeded", "failed", "cancelled"}:
                return status

            if status.metrics:
                await self._training_service.record_runtime_metrics(
                    user_id=user_id,
                    job_id=job_id,
                    payload=status.model_dump(mode="json"),
                )

            await asyncio.sleep(self._poll_interval_seconds)

        raise RuntimeAgentError(f"Training timed out after {self._poll_timeout_seconds} seconds.")

    async def _raise_if_cancelled(self, user_id: UUID, job_id: UUID) -> None:
        if await self._is_cancelled(user_id, job_id):
            raise TrainingJobCancelled()

    async def _is_cancelled(self, user_id: UUID, job_id: UUID) -> bool:
        job = await self._training_service.get_job(user_id, job_id)
        return job.status == TrainingJobStatus.CANCELLED

    def _require_local_dataset(self, normalized_dataset_path: str) -> Path:
        path = Path(normalized_dataset_path).resolve()
        if not path.exists():
            raise FileNotFoundError("Normalized dataset file does not exist.")
        return path

    async def _cleanup_runtime(self, client: RuntimeAgentClient, user_id: UUID, job_id: UUID) -> None:
        try:
            await client.cleanup()
        except Exception as exc:
            await self._training_service.record_event(
                user_id=user_id,
                job_id=job_id,
                message="GPU runtime cleanup failed.",
                metadata={"error": str(exc)},
            )

    async def _terminate_gpu(self, gpu_instance_id: UUID, user_id: UUID, job_id: UUID) -> None:
        try:
            await self._gpu_service.terminate_instance(user_id=user_id, instance_id=gpu_instance_id)
        except Exception as exc:
            await self._training_service.record_event(
                user_id=user_id,
                job_id=job_id,
                message="GPU termination failed.",
                metadata={"error": str(exc), "gpu_instance_id": str(gpu_instance_id)},
            )

    @staticmethod
    def _runtime_config(job: TrainingJob, remote_dataset_path: str) -> dict:
        return {
            "job_id": str(job.id),
            "model_key": job.model_key,
            "template_name": job.template_name,
            "dataset_path": remote_dataset_path,
            "training_config": job.training_config.model_dump(mode="json"),
        }

    @staticmethod
    def _artifact_type(path: str) -> str:
        # The runner lays artifacts out as adapter/, tokenizer/ and checkpoints/, so the
        # folder says what a file is more reliably than its extension.
        parts = Path(path).parts
        filename = parts[-1].lower() if parts else ""
        if "checkpoints" in parts:
            return "checkpoint"
        if "adapter" in parts:
            if filename == "adapter_config.json":
                return "adapter_config"
            if filename.endswith(".safetensors"):
                return "adapter_model"
            return "adapter"
        if "tokenizer" in parts:
            return "tokenizer"
        if filename == "training_config.json":
            return "training_config"
        if filename.endswith((".log", ".txt")):
            return "log"
        return "other"

    async def _transition(
        self,
        job: TrainingJob,
        to_status: TrainingJobStatus,
        message: str,
        gpu_instance_id: UUID | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> TrainingJob:
        return await self._training_service.transition_job(
            user_id=job.user_id,
            job_id=job.id,
            next_status=to_status,
            message=message,
            gpu_instance_id=gpu_instance_id,
            error_message=error_message,
            metadata=metadata,
        )
