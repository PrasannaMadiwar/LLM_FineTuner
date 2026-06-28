from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_gpu_service
from app.domain.gpu import (
    GPUCommandResult,
    GPUHealthResult,
    GPUInstance,
    GPUInstanceStatus,
    GPUProviderName,
)
from app.domain.users import User, UserRole
from app.main import app


class FakeGPUService:
    def __init__(self):
        self.user_id = uuid4()
        now = datetime.now(UTC)
        self.instance = GPUInstance(
            id=uuid4(),
            provider=GPUProviderName.RUNPOD,
            provider_instance_id="pod-1",
            status=GPUInstanceStatus.RUNNING,
            user_id=self.user_id,
            gpu_type="A100",
            created_at=now,
            updated_at=now,
        )

    async def create_instance(self, user_id, config, project_id=None):
        return self.instance.model_copy(update={"user_id": user_id, "project_id": project_id})

    async def terminate_instance(self, user_id, instance_id):
        return self.instance.model_copy(update={"status": GPUInstanceStatus.STOPPING})

    async def get_instance(self, user_id, instance_id):
        return self.instance

    async def list_instances(self, user_id):
        return [self.instance]

    async def execute_command(self, user_id, instance_id, command):
        return GPUCommandResult(stdout="ok", stderr="", exit_code=0, execution_time_seconds=0.1)

    async def upload_files(self, user_id, instance_id, files):
        from app.domain.gpu import GPUUploadResult

        return GPUUploadResult(files=["/workspace/data.jsonl"], bytes_uploaded=4, duration_seconds=0.1)

    async def health_check(self, user_id, instance_id):
        return GPUHealthResult(healthy=True, status=GPUInstanceStatus.RUNNING, message="ok")

    async def stream_logs(self, user_id, instance_id):
        from app.domain.gpu import GPULogEntry

        yield GPULogEntry(stream="stdout", message="ready")


def test_gpu_create_api_requires_auth_context_and_returns_instance():
    service = FakeGPUService()
    client = _client(service)

    response = client.post("/api/v1/gpu/create", json={"gpu_type": "A100"})

    assert response.status_code == 200
    assert response.json()["instance"]["provider_instance_id"] == "pod-1"


def test_gpu_execute_api():
    service = FakeGPUService()
    client = _client(service)

    response = client.post(
        f"/api/v1/gpu/{service.instance.id}/execute",
        json={"command": "ls /workspace"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["stdout"] == "ok"


def test_gpu_logs_api():
    service = FakeGPUService()
    client = _client(service)

    response = client.get(f"/api/v1/gpu/{service.instance.id}/logs")

    assert response.status_code == 200
    assert response.json()["entries"][0]["message"] == "ready"


def test_gpu_health_api():
    service = FakeGPUService()
    client = _client(service)

    response = client.get(f"/api/v1/gpu/{service.instance.id}/health")

    assert response.status_code == 200
    assert response.json()["health"]["healthy"] is True


def _client(service):
    user = User(
        id=service.user_id,
        email="gpu@example.com",
        hashed_password="hash",
        role=UserRole.USER,
        is_active=True,
    )
    app.dependency_overrides[get_gpu_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)
