import asyncio
from datetime import UTC, datetime
from itertools import pairwise, product
from uuid import uuid4

import pytest

from app.domain.gpu import (
    GPUCreateConfig,
    GPUErrorCode,
    GPUEvent,
    GPUHealthResult,
    GPUInstance,
    GPUInstanceStatus,
    GPUProviderError,
    GPUProviderInstance,
    GPUProviderName,
    GPUStatusResult,
)
from app.domain.training import TrainingJobStatus
from app.infrastructure.gpu.base import GPUProvider, GPUProviderException
from app.services.gpu_service import GPUService
from app.services.training_state_machine import TrainingStateMachine

S = TrainingJobStatus

# Written out independently of TrainingStateMachine so a change to the table fails here.
EXPECTED_JOB_TRANSITIONS = {
    S.CREATED: {S.QUEUED, S.CANCELLED},
    S.QUEUED: {S.PREPARING, S.FAILED, S.CANCELLED},
    S.PREPARING: {S.WAITING_GPU, S.FAILED, S.CANCELLED},
    S.WAITING_GPU: {S.GPU_READY, S.FAILED, S.CANCELLED},
    S.GPU_READY: {S.UPLOADING, S.FAILED, S.CANCELLED},
    S.UPLOADING: {S.STARTING, S.FAILED, S.CANCELLED},
    S.STARTING: {S.TRAINING, S.FAILED, S.CANCELLED},
    S.TRAINING: {S.CHECKPOINTING, S.COLLECTING_ARTIFACTS, S.FAILED, S.CANCELLED},
    S.CHECKPOINTING: {S.TRAINING, S.COLLECTING_ARTIFACTS, S.FAILED, S.CANCELLED},
    S.COLLECTING_ARTIFACTS: {S.COMPLETED, S.FAILED},
    S.COMPLETED: set(),
    S.FAILED: set(),
    S.CANCELLED: set(),
}
ALLOWED = [(src, dst) for src, targets in EXPECTED_JOB_TRANSITIONS.items() for dst in targets]
REJECTED = [
    (src, dst)
    for src, dst in product(TrainingJobStatus, TrainingJobStatus)
    if dst not in EXPECTED_JOB_TRANSITIONS[src]
]


def test_expected_table_covers_every_job_status():
    assert set(EXPECTED_JOB_TRANSITIONS) == set(TrainingJobStatus)


@pytest.mark.parametrize(("current", "target"), ALLOWED)
def test_job_state_machine_allows_listed_transition(current, target):
    TrainingStateMachine().validate_transition(current, target)


@pytest.mark.parametrize(("current", "target"), REJECTED)
def test_job_state_machine_rejects_unlisted_transition(current, target):
    with pytest.raises(ValueError):
        TrainingStateMachine().validate_transition(current, target)


def test_job_happy_path_reaches_completed():
    machine = TrainingStateMachine()
    path = [
        S.CREATED, S.QUEUED, S.PREPARING, S.WAITING_GPU, S.GPU_READY, S.UPLOADING,
        S.STARTING, S.TRAINING, S.CHECKPOINTING, S.TRAINING, S.COLLECTING_ARTIFACTS, S.COMPLETED,
    ]
    for current, target in pairwise(path):
        machine.validate_transition(current, target)


class ScriptedGPUProvider(GPUProvider):
    """In-memory GPUProvider: reports a scripted sequence of statuses, no GPU required."""

    def __init__(
        self,
        statuses: list[GPUInstanceStatus],
        healthy: bool = True,
        create_error: GPUProviderError | None = None,
        terminate_status: GPUInstanceStatus = GPUInstanceStatus.STOPPED,
    ):
        self._statuses = list(statuses)
        self._healthy = healthy
        self._create_error = create_error
        self._terminate_status = terminate_status
        self.terminated: list[str] = []

    async def create_instance(self, config):
        if self._create_error:
            raise GPUProviderException(self._create_error)
        return GPUProviderInstance(provider_instance_id="fake-pod", status=GPUInstanceStatus.STARTING)

    async def terminate_instance(self, provider_instance_id):
        self.terminated.append(provider_instance_id)
        return GPUStatusResult(provider_instance_id=provider_instance_id, status=self._terminate_status)

    async def get_status(self, provider_instance_id):
        status = self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=status,
            endpoint_url="http://fake-pod:8001",
        )

    async def health_check(self, provider_instance_id):
        return GPUHealthResult(
            healthy=self._healthy,
            status=GPUInstanceStatus.RUNNING,
            message=None if self._healthy else "agent not responding",
        )

    async def upload_files(self, provider_instance_id, files):
        raise NotImplementedError

    async def download_files(self, provider_instance_id, remote_path):
        raise NotImplementedError

    async def execute_command(self, provider_instance_id, command):
        raise NotImplementedError

    async def stream_logs(self, provider_instance_id):
        if False:
            yield

    async def list_instances(self):
        return []


class RecordingGPURepository:
    def __init__(self):
        self.instances: dict = {}
        self.history: list[GPUInstanceStatus] = []
        self.events: list[GPUEvent] = []

    async def create_instance(self, user_id, provider, status, project_id=None, gpu_type=None, metadata=None):
        now = datetime.now(UTC)
        instance = GPUInstance(
            id=uuid4(),
            provider=provider,
            status=status,
            user_id=user_id,
            project_id=project_id,
            gpu_type=gpu_type,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self.instances[instance.id] = instance
        self.history.append(status)
        return instance

    async def get_instance(self, instance_id):
        return self.instances.get(instance_id)

    async def update_instance(self, instance_id, **kwargs):
        payload = self.instances[instance_id].model_dump()
        payload.update({key: value for key, value in kwargs.items() if value is not None})
        updated = GPUInstance(**payload)
        self.instances[instance_id] = updated
        if not self.history or self.history[-1] != updated.status:
            self.history.append(updated.status)
        return updated

    async def add_event(self, user_id, event_type, message, gpu_instance_id=None, metadata=None):
        event = GPUEvent(
            id=uuid4(),
            gpu_instance_id=gpu_instance_id,
            user_id=user_id,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event


def _gpu_service(provider: GPUProvider, repository: RecordingGPURepository, timeout: int = 5) -> GPUService:
    return GPUService(
        repository=repository,
        provider=provider,
        provider_name=GPUProviderName.LOCAL,
        create_timeout_seconds=timeout,
        operation_max_retries=0,
        poll_interval_seconds=0,
    )


G = GPUInstanceStatus


def test_gpu_instance_moves_pending_starting_running():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.STARTING, G.STARTING, G.RUNNING])

    instance = asyncio.run(_gpu_service(provider, repository).create_instance(uuid4(), GPUCreateConfig()))

    assert instance.status == G.RUNNING
    assert repository.history == [G.PENDING, G.STARTING, G.RUNNING]
    assert provider.terminated == []


@pytest.mark.parametrize("reported", [G.FAILED, G.UNAVAILABLE])
def test_gpu_instance_fails_and_is_cleaned_up_when_provider_reports_failure(reported):
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.STARTING, reported])

    with pytest.raises(GPUProviderException) as exc_info:
        asyncio.run(_gpu_service(provider, repository).create_instance(uuid4(), GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.GPU_UNAVAILABLE
    assert repository.history == [G.PENDING, G.STARTING, G.FAILED]
    assert provider.terminated == ["fake-pod"]


def test_gpu_instance_fails_when_health_check_fails_after_running():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.RUNNING], healthy=False)

    with pytest.raises(GPUProviderException):
        asyncio.run(_gpu_service(provider, repository).create_instance(uuid4(), GPUCreateConfig()))

    assert repository.history == [G.PENDING, G.STARTING, G.RUNNING, G.FAILED]
    assert provider.terminated == ["fake-pod"]


def test_gpu_instance_fails_on_ready_timeout():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.STARTING])

    with pytest.raises(GPUProviderException) as exc_info:
        asyncio.run(_gpu_service(provider, repository, timeout=0).create_instance(uuid4(), GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.TIMEOUT
    assert repository.history[-1] == G.FAILED
    assert provider.terminated == ["fake-pod"]


def test_gpu_instance_fails_without_cleanup_when_provider_rejects_create():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider(
        [G.RUNNING],
        create_error=GPUProviderError(code=GPUErrorCode.API_ERROR, message="bad request", status_code=400),
    )

    with pytest.raises(GPUProviderException):
        asyncio.run(_gpu_service(provider, repository).create_instance(uuid4(), GPUCreateConfig()))

    assert repository.history == [G.PENDING, G.FAILED]
    assert provider.terminated == []


def test_gpu_instance_terminates_through_stopping_to_stopped():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.RUNNING])
    service = _gpu_service(provider, repository)
    user_id = uuid4()
    instance = asyncio.run(service.create_instance(user_id, GPUCreateConfig()))

    stopped = asyncio.run(service.terminate_instance(user_id, instance.id))

    assert stopped.status == G.STOPPED
    assert stopped.terminated_at is not None
    assert repository.history[-3:] == [G.RUNNING, G.STOPPING, G.STOPPED]


def test_gpu_instance_cannot_be_terminated_by_another_user():
    repository = RecordingGPURepository()
    provider = ScriptedGPUProvider([G.RUNNING])
    service = _gpu_service(provider, repository)
    instance = asyncio.run(service.create_instance(uuid4(), GPUCreateConfig()))

    with pytest.raises(PermissionError):
        asyncio.run(service.terminate_instance(uuid4(), instance.id))

    assert repository.instances[instance.id].status == G.RUNNING
    assert provider.terminated == []
