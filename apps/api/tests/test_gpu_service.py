import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.gpu import (
    GPUCommand,
    GPUCommandResult,
    GPUCreateConfig,
    GPUEvent,
    GPUEventType,
    GPUHealthResult,
    GPUInstance,
    GPUInstanceStatus,
    GPUProviderInstance,
    GPUProviderName,
    GPUStatusResult,
)
from app.services.gpu_service import GPUService


class FakeGPURepository:
    def __init__(self):
        self.instances = {}
        self.events = []

    async def create_instance(self, user_id, provider, status, project_id=None, gpu_type=None, metadata=None):
        now = datetime.now(UTC)
        instance = GPUInstance(
            id=uuid4(),
            provider=provider,
            provider_instance_id=None,
            status=status,
            user_id=user_id,
            project_id=project_id,
            gpu_type=gpu_type,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self.instances[instance.id] = instance
        return instance

    async def get_instance(self, instance_id):
        return self.instances.get(instance_id)

    async def list_instances(self, user_id):
        return [instance for instance in self.instances.values() if instance.user_id == user_id]

    async def update_instance(self, instance_id, **kwargs):
        instance = self.instances[instance_id]
        payload = instance.model_dump()
        payload.update({key: value for key, value in kwargs.items() if value is not None})
        payload["updated_at"] = datetime.now(UTC)
        updated = GPUInstance(**payload)
        self.instances[instance_id] = updated
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


class FakeGPUProvider:
    def __init__(self):
        self.terminated = False
        self.commands = []

    async def create_instance(self, config):
        return GPUProviderInstance(
            provider_instance_id="pod-123",
            status=GPUInstanceStatus.STARTING,
            endpoint_url="http://pod.test",
            metadata={"id": "pod-123"},
        )

    async def terminate_instance(self, provider_instance_id):
        self.terminated = True
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=GPUInstanceStatus.STOPPING,
        )

    async def get_status(self, provider_instance_id):
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=GPUInstanceStatus.RUNNING,
            endpoint_url="http://pod.test",
            metadata={"id": provider_instance_id},
        )

    async def upload_files(self, provider_instance_id, files):
        raise NotImplementedError

    async def download_files(self, provider_instance_id, remote_path):
        raise NotImplementedError

    async def execute_command(self, provider_instance_id, command):
        self.commands.append(command.command)
        return GPUCommandResult(stdout="ok", stderr="", exit_code=0, execution_time_seconds=0.2)

    async def stream_logs(self, provider_instance_id):
        if False:
            yield

    async def health_check(self, provider_instance_id):
        return GPUHealthResult(
            healthy=True,
            status=GPUInstanceStatus.RUNNING,
            message="ok",
        )

    async def list_instances(self):
        return []


def test_gpu_service_creates_waits_health_checks_and_records_events():
    repository = FakeGPURepository()
    provider = FakeGPUProvider()
    user_id = uuid4()
    service = GPUService(
        repository,
        provider,
        provider_name=GPUProviderName.RUNPOD,
        poll_interval_seconds=0,
        operation_max_retries=0,
    )

    instance = asyncio.run(service.create_instance(user_id, GPUCreateConfig(gpu_type="A100")))

    assert instance.provider_instance_id == "pod-123"
    assert instance.status == GPUInstanceStatus.RUNNING
    assert GPUEventType.INSTANCE_READY in {event.event_type for event in repository.events}


def test_gpu_service_enforces_instance_ownership():
    repository = FakeGPURepository()
    provider = FakeGPUProvider()
    owner_id = uuid4()
    other_user_id = uuid4()
    service = GPUService(repository, provider, operation_max_retries=0)
    instance = asyncio.run(service.create_instance(owner_id, GPUCreateConfig()))

    with pytest.raises(PermissionError):
        asyncio.run(service.get_instance(other_user_id, instance.id, refresh=False))


def test_gpu_service_rejects_unsupported_commands():
    repository = FakeGPURepository()
    provider = FakeGPUProvider()
    user_id = uuid4()
    service = GPUService(repository, provider, operation_max_retries=0)
    instance = asyncio.run(service.create_instance(user_id, GPUCreateConfig()))

    with pytest.raises(ValueError):
        asyncio.run(service.execute_command(user_id, instance.id, GPUCommand(command="curl http://example.com")))


def test_gpu_service_executes_allowed_command():
    repository = FakeGPURepository()
    provider = FakeGPUProvider()
    user_id = uuid4()
    service = GPUService(repository, provider, operation_max_retries=0)
    instance = asyncio.run(service.create_instance(user_id, GPUCreateConfig()))

    result = asyncio.run(service.execute_command(user_id, instance.id, GPUCommand(command="ls /workspace")))

    assert result.exit_code == 0
    assert provider.commands == ["ls /workspace"]
