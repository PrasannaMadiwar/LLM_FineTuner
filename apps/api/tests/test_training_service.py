import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.training import (
    ModelDefinition,
    TrainingConfig,
    TrainingJob,
    TrainingJobEvent,
    TrainingJobStatus,
)
from app.services.model_registry import ModelRegistry
from app.services.training_service import TrainingService
from app.services.training_state_machine import TrainingStateMachine


class FakeTrainingJobRepository:
    def __init__(self):
        self.jobs = {}
        self.events = []

    async def create_job(
        self,
        user_id,
        status,
        model_key,
        model_id,
        template_name,
        training_config,
        dataset_id,
        normalized_dataset_path,
        project_id=None,
    ):
        now = datetime.now(UTC)
        job = TrainingJob(
            id=uuid4(),
            user_id=user_id,
            project_id=project_id,
            status=status,
            model_key=model_key,
            model_id=model_id,
            template_name=template_name,
            training_config=training_config,
            dataset_id=dataset_id,
            normalized_dataset_path=normalized_dataset_path,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        await self.add_event(job.id, user_id, None, status, "Training job created.")
        return job

    async def get_job(self, job_id):
        return self.jobs.get(job_id)

    async def list_jobs(self, user_id):
        return [job for job in self.jobs.values() if job.user_id == user_id]

    async def update_job(self, job_id, **kwargs):
        job = self.jobs[job_id]
        payload = job.model_dump()
        payload.update({key: value for key, value in kwargs.items() if value is not None})
        payload["updated_at"] = datetime.now(UTC)
        updated = TrainingJob(**payload)
        self.jobs[job_id] = updated
        return updated

    async def add_event(
        self,
        training_job_id,
        user_id,
        from_status,
        to_status,
        message,
        metadata=None,
    ):
        event = TrainingJobEvent(
            id=uuid4(),
            training_job_id=training_job_id,
            user_id=user_id,
            from_status=from_status,
            to_status=to_status,
            message=message,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event

    async def list_events(self, job_id):
        return [event for event in self.events if event.training_job_id == job_id]


class FakeTemplateLoader:
    def list_templates(self):
        return ["llama"]

    def resolve_template(self, template_name):
        if template_name != "llama":
            raise ValueError("Training template is not installed.")
        return template_name


class FakeTaskDispatcher:
    def __init__(self):
        self.dispatched = []

    def dispatch(self, user_id, job_id):
        self.dispatched.append((user_id, job_id))
        return "task-123"


def test_training_service_creates_and_queues_job():
    repository = FakeTrainingJobRepository()
    service = _service(repository)
    user_id = uuid4()

    job = asyncio.run(service.create_job(user_id, _config()))
    queued = asyncio.run(service.queue_job(user_id, job.id))

    assert job.status == TrainingJobStatus.CREATED
    assert queued.status == TrainingJobStatus.QUEUED
    assert queued.template_name == "llama"
    assert queued.training_config.max_sequence_length == 4096


def test_training_service_dispatches_worker_task_when_configured():
    repository = FakeTrainingJobRepository()
    dispatcher = FakeTaskDispatcher()
    service = _service(repository, task_dispatcher=dispatcher)
    user_id = uuid4()
    job = asyncio.run(service.create_job(user_id, _config()))

    asyncio.run(service.queue_job(user_id, job.id))

    assert dispatcher.dispatched == [(user_id, job.id)]
    assert repository.events[-1].metadata == {"celery_task_id": "task-123"}


def test_training_service_enforces_ownership():
    repository = FakeTrainingJobRepository()
    service = _service(repository)
    job = asyncio.run(service.create_job(uuid4(), _config()))

    with pytest.raises(PermissionError):
        asyncio.run(service.get_job(uuid4(), job.id))


def test_training_service_rejects_unsupported_model():
    service = _service(FakeTrainingJobRepository())

    with pytest.raises(ValueError):
        asyncio.run(
            service.create_job(
                uuid4(),
                _config().model_copy(update={"model_key": "unknown"}),
            )
        )


def _service(repository, task_dispatcher=None):
    registry = ModelRegistry(
        [
            ModelDefinition(
                model_key="llama-test",
                model_id="meta-llama/test",
                display_name="Llama Test",
                huggingface_repo="meta-llama/test",
                template="llama",
                sequence_length=4096,
            )
        ]
    )
    return TrainingService(
        repository=repository,
        model_registry=registry,
        template_loader=FakeTemplateLoader(),
        state_machine=TrainingStateMachine(),
        task_dispatcher=task_dispatcher,
    )


def _config():
    return TrainingConfig(
        model_key="llama-test",
        dataset_id="demo",
        normalized_dataset_path="datasets/demo.jsonl",
    )
