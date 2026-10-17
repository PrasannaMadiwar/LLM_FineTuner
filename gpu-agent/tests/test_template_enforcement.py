import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import settings, training_service, workspace_service
from app.main import app
from app.models.schemas import CommandRequest, TrainingRequest
from app.services.file_service import FileService
from app.services.log_service import LogService
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService

REPO_TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def test_approved_template_set_is_exactly_the_shipped_templates():
    shipped = {path.parent.name for path in REPO_TEMPLATES.glob("*/train.py")}

    assert TrainingService._APPROVED_TEMPLATES == {"llama", "qwen", "gemma", "mistral"}
    assert shipped == TrainingService._APPROVED_TEMPLATES


@pytest.mark.parametrize("template", ["llama", "qwen", "gemma", "mistral", "  QWEN ", "Llama"])
def test_approved_templates_are_accepted_after_normalizing(tmp_path, template):
    service, _ = _service(tmp_path)

    assert service._validate_template(template) == template.strip().lower()


@pytest.mark.parametrize(
    "template",
    [
        "custom",
        "common",
        "phi",
        "qwen2",
        "../qwen",
        "qwen/../../etc",
        "templates/qwen",
        "/workspace/templates/qwen",
        "qwen;rm -rf /",
        " ",
    ],
)
def test_unapproved_template_is_rejected_before_anything_is_written(tmp_path, template):
    service, workspace = _service(tmp_path)
    workspace.validate_path("dataset/train.jsonl").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="not approved"):
        asyncio.run(
            service.start_training(TrainingRequest(template=template, dataset_path="dataset/train.jsonl"))
        )

    assert list((tmp_path / "configs").iterdir()) == []
    assert service._records == {}


def test_train_endpoint_returns_422_for_unapproved_template(tmp_path):
    client, workspace = _client(tmp_path)
    workspace.validate_path("dataset/train.jsonl").write_text("{}", encoding="utf-8")

    response = client.post("/train", json={"template": "evil", "dataset_path": "dataset/train.jsonl"})

    assert response.status_code == 422
    assert "not approved" in response.json()["detail"]


@pytest.mark.parametrize(
    "command",
    [
        "python /tmp/malicious.py",
        "python -c 'import os'",
        "python",
        "python templates/../evil.py",
        "python3 templates/qwen/train.py",
        "pip install requests",
        "pip",
        "bash -c id",
        "sh script.sh",
        "curl http://example.com",
        "rm -rf /workspace",
        "",
    ],
)
def test_commands_outside_allowlist_or_template_dirs_are_rejected(tmp_path, command):
    service, _ = _service(tmp_path)

    with pytest.raises(ValueError):
        asyncio.run(service.execute_command(CommandRequest(command=command)))


def test_python_may_target_a_shipped_template_script(tmp_path):
    service, _ = _service(tmp_path)

    service._validate_python_command(["python", str(REPO_TEMPLATES / "qwen" / "train.py")])


def test_python_may_target_a_template_in_the_workspace_template_dir(tmp_path):
    service, _ = _service(tmp_path)
    script = tmp_path / "templates" / "qwen" / "train.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")

    service._validate_python_command(["python", "templates/qwen/train.py"])


def test_commands_endpoint_returns_422_for_disallowed_command(tmp_path):
    client, _ = _client(tmp_path)

    response = client.post("/commands", json={"command": "bash -c id"})

    assert response.status_code == 422


def _settings(root: Path) -> Settings:
    return Settings(
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
        agent_token="test-token",
    )


def _service(root: Path):
    configured = _settings(root)
    workspace = WorkspaceService(configured)
    workspace.ensure_workspace()
    file_service = FileService(configured, workspace)
    log_service = LogService(workspace)
    return TrainingService(configured, workspace, file_service, log_service), workspace


def _client(root: Path):
    service, workspace = _service(root)
    app.dependency_overrides[settings] = lambda: _settings(root)
    app.dependency_overrides[workspace_service] = lambda: workspace
    app.dependency_overrides[training_service] = lambda: service
    return TestClient(app, headers={"Authorization": "Bearer test-token"}), workspace
