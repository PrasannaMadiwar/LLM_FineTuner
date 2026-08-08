import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import pytest

from app.domain.gpu import GPUInstance, GPUInstanceStatus, GPUProviderName
from app.domain.training import TrainingConfig, TrainingJob, TrainingJobEvent, TrainingJobStatus
from app.services.training_orchestrator import TrainingOrchestrator


class FakeTrainingService:
    def __init__(self, job):
        self.job = job
        self.events = []

    async def get_job(self, user_id, job_id):
        if self.job.user_id != user_id or self.job.id != job_id:
            raise ValueError("Training job not found.")
        return self.job

    async def transition_job(
        self,
        user_id,
        job_id,
        next_status,
        message,
        metadata=None,
        gpu_instance_id=None,
        error_message=None,
        queued_at=None,
    ):
        previous = self.job.status
        payload = self.job.model_dump()
        payload.update(
            {
                "status": next_status,
                "gpu_instance_id": gpu_instance_id or self.job.gpu_instance_id,
                "error_message": error_message or self.job.error_message,
                "updated_at": datetime.now(UTC),
            }
        )
        self.job = TrainingJob(**payload)
        self.events.append(
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=job_id,
                user_id=user_id,
                from_status=previous,
                to_status=next_status,
                message=message,
                metadata=metadata or {},
                created_at=datetime.now(UTC),
            )
        )
        return self.job

    async def record_event(self, user_id, job_id, message, metadata=None):
        self.events.append(
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=job_id,
                user_id=user_id,
                from_status=self.job.status,
                to_status=self.job.status,
                message=message,
                metadata=metadata or {},
                created_at=datetime.now(UTC),
            )
        )

    async def record_runtime_metrics(self, user_id, job_id, payload):
        self.events.append(
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=job_id,
                user_id=user_id,
                from_status=self.job.status,
                to_status=self.job.status,
                message="metrics",
                metadata=payload,
                created_at=datetime.now(UTC),
            )
        )

    async def record_checkpoint(self, user_id, job_id, path, metadata=None):
        self.events.append(
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=job_id,
                user_id=user_id,
                from_status=self.job.status,
                to_status=self.job.status,
                message="checkpoint",
                metadata={"path": path, **(metadata or {})},
                created_at=datetime.now(UTC),
            )
        )

    async def record_artifact(self, **kwargs):
        self.events.append(
            TrainingJobEvent(
                id=uuid4(),
                training_job_id=kwargs["job_id"],
                user_id=kwargs["user_id"],
                from_status=self.job.status,
                to_status=self.job.status,
                message="artifact",
                metadata=kwargs,
                created_at=datetime.now(UTC),
            )
        )


class FakeGPUService:
    def __init__(self):
        self.terminated = False

    async def create_instance(self, user_id, config, project_id=None):
        now = datetime.now(UTC)
        return GPUInstance(
            id=uuid4(),
            provider=GPUProviderName.RUNPOD,
            provider_instance_id="pod-1",
            status=GPUInstanceStatus.RUNNING,
            user_id=user_id,
            project_id=project_id,
            endpoint_url="http://agent.test",
            created_at=now,
            updated_at=now,
        )

    async def terminate_instance(self, user_id, instance_id):
        self.terminated = True


class FakeRuntimeAgentClient:
    uploaded: ClassVar[list] = []
    cleaned = False

    def __init__(self, base_url):
        self.base_url = base_url

    async def health(self):
        return {"status": "ok"}

    async def upload_file(self, local_path: Path, remote_path: str):
        self.uploaded.append((str(local_path), remote_path))

    async def upload_json(self, remote_path: str, payload: dict):
        self.uploaded.append((payload["training_job_id"], remote_path))

    async def start_training(self, template, dataset_path, config):
        from app.infrastructure.runtime_agent_client import RuntimeTrainingStart

        return RuntimeTrainingStart(training_id="run-1", state="queued")

    async def status(self, training_id):
        from app.infrastructure.runtime_agent_client import RuntimeTrainingStatus

        return RuntimeTrainingStatus(
            training_id=training_id,
            state="succeeded",
            loss=0.1,
            metrics={"loss": 0.1},
            checkpoints=["artifacts/run-1/checkpoints/checkpoint-1"],
        )

    async def artifacts(self, training_id):
        from app.infrastructure.runtime_agent_client import RuntimeArtifactList

        return RuntimeArtifactList(training_id=training_id, artifacts=[])

    async def cleanup(self):
        type(self).cleaned = True
        return {"deleted_paths": [], "bytes_deleted": 0}


def test_training_orchestrator_runs_agent_workflow_and_cleans_gpu(tmp_path):
    dataset = tmp_path / "train.jsonl"
    dataset.write_text('{"messages":[]}\n', encoding="utf-8")
    job = _job(dataset)
    training_service = FakeTrainingService(job)
    gpu_service = FakeGPUService()
    orchestrator = TrainingOrchestrator(
        training_service=training_service,
        gpu_service=gpu_service,
        runtime_client_factory=FakeRuntimeAgentClient,
        poll_interval_seconds=0,
        poll_timeout_seconds=1,
    )

    completed = asyncio.run(orchestrator.run_job(job.user_id, job.id))

    assert completed.status == TrainingJobStatus.COMPLETED
    assert gpu_service.terminated is True
    assert FakeRuntimeAgentClient.cleaned is True
    assert TrainingJobStatus.TRAINING in {event.to_status for event in training_service.events}
    assert TrainingJobStatus.CHECKPOINTING in {event.to_status for event in training_service.events}


def test_training_orchestrator_fails_when_dataset_is_missing(tmp_path):
    job = _job(tmp_path / "missing.jsonl")
    training_service = FakeTrainingService(job)
    orchestrator = TrainingOrchestrator(
        training_service=training_service,
        gpu_service=FakeGPUService(),
        runtime_client_factory=FakeRuntimeAgentClient,
        poll_interval_seconds=0,
        poll_timeout_seconds=1,
    )

    with pytest.raises(FileNotFoundError):
        asyncio.run(orchestrator.run_job(job.user_id, job.id))

    assert training_service.job.status == TrainingJobStatus.FAILED


def _job(dataset_path: Path) -> TrainingJob:
    now = datetime.now(UTC)
    return TrainingJob(
        id=uuid4(),
        user_id=uuid4(),
        status=TrainingJobStatus.QUEUED,
        model_key="llama-test",
        model_id="meta-llama/test",
        template_name="llama",
        training_config=TrainingConfig(
            model_key="llama-test",
            dataset_id="demo",
            normalized_dataset_path=str(dataset_path),
        ),
        dataset_id="demo",
        normalized_dataset_path=str(dataset_path),
        created_at=now,
        updated_at=now,
    )
