from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import (
    file_service,
    health_service,
    log_service,
    settings,
    training_service,
    workspace_service,
)
from app.main import app
from app.services.file_service import FileService
from app.services.health_service import HealthService
from app.services.log_service import LogService
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService


def test_health_endpoint(tmp_path):
    client = _client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_agent_rejects_missing_or_invalid_token(tmp_path):
    client = _client(tmp_path, agent_token="secret-token")

    missing = client.get("/health")
    invalid = client.get("/health", headers={"Authorization": "Bearer wrong"})
    valid = client.get("/health", headers={"Authorization": "Bearer secret-token"})

    assert missing.status_code == 401
    assert invalid.status_code == 403
    assert valid.status_code == 200


def test_upload_and_file_metadata_endpoints(tmp_path):
    client = _client(tmp_path)

    upload = client.put("/files", params={"path": "dataset/train.txt"}, content=b"hello")
    metadata = client.get("/files", params={"path": "dataset/train.txt"})

    assert upload.status_code == 200
    assert upload.json()["bytes_uploaded"] == 5
    assert metadata.json()["bytes_downloaded"] == 5


def test_train_status_logs_and_artifacts_endpoints(tmp_path):
    client = _client(tmp_path)
    client.put(
        "/files",
        params={"path": "dataset/train.jsonl"},
        content=b'{"messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"hello"}]}',
    )

    start = client.post(
        "/train",
        json={"template": "llama", "dataset_path": "dataset/train.jsonl", "config": {"dry_run": True}},
    )
    training_id = start.json()["training_id"]
    status = _wait_for_status(client, training_id)
    logs = client.get(f"/logs/{training_id}")
    artifacts = client.get(f"/artifacts/{training_id}")

    assert start.status_code == 200
    assert status["state"] == "succeeded"
    assert status["metrics"]["dry_run"] is True
    assert status["checkpoints"]
    assert logs.status_code == 200
    assert artifacts.json()["artifacts"]


def _wait_for_status(client: TestClient, training_id: str) -> dict:
    import time

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/status/{training_id}")
        payload = response.json()
        if payload["state"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("Training run did not finish.")


def _client(root: Path, agent_token: str | None = None) -> TestClient:
    app.dependency_overrides.clear()
    configured = Settings(
        workspace_path=root,
        dataset_path=root / "dataset",
        config_path=root / "configs",
        template_path=root / "templates",
        output_path=root / "outputs",
        checkpoint_path=root / "checkpoints",
        log_path=root / "logs",
        artifact_path=root / "artifacts",
        cache_path=root / "cache",
        temp_path=root / "temp",
        port=8001,
        max_upload_bytes=1024,
        container_started_at=0,
        agent_token=agent_token,
    )
    workspace = WorkspaceService(configured)
    workspace.ensure_workspace()
    files = FileService(configured, workspace)
    logs = LogService(workspace)
    training = TrainingService(configured, workspace, files, logs)
    health = HealthService(configured, workspace)
    app.dependency_overrides[settings] = lambda: configured
    app.dependency_overrides[workspace_service] = lambda: workspace
    app.dependency_overrides[file_service] = lambda: files
    app.dependency_overrides[log_service] = lambda: logs
    app.dependency_overrides[training_service] = lambda: training
    app.dependency_overrides[health_service] = lambda: health
    return TestClient(app)
