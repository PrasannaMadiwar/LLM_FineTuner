import asyncio
from pathlib import Path

import pytest

from app.config import Settings
from app.models.schemas import CommandRequest, TrainingRequest, TrainingState
from app.services.file_service import FileService
from app.services.log_service import LogService
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService


@pytest.mark.parametrize("template", ["llama", "qwen", "gemma", "mistral"])
def test_training_service_runs_approved_template_dry_run(tmp_path, template):
    service, workspace = _service(tmp_path)
    dataset = workspace.validate_path("dataset/train.jsonl")
    dataset.write_text(
        '{"messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"hello"}]}',
        encoding="utf-8",
    )

    record = asyncio.run(
        service.start_training(
            TrainingRequest(
                template=template,
                dataset_path="dataset/train.jsonl",
                config={"dry_run": True},
            )
        )
    )
    _wait_for_finish(service, record.training_id)
    status = service.status(record.training_id)
    artifact_paths = {artifact["path"] for artifact in service.artifacts(record.training_id)}

    assert status.state == TrainingState.SUCCEEDED
    assert status.current_epoch == 1
    assert status.loss == 0.0
    assert any("adapter/adapter_config.json" in path for path in artifact_paths)
    assert any("tokenizer/tokenizer_config.json" in path for path in artifact_paths)
    assert any("checkpoints/checkpoint-1/adapter_model.safetensors" in path for path in artifact_paths)


def test_training_service_rejects_unapproved_template(tmp_path):
    service, workspace = _service(tmp_path)
    workspace.validate_path("dataset/train.jsonl").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        asyncio.run(
            service.start_training(
                TrainingRequest(template="custom", dataset_path="dataset/train.jsonl", config={})
            )
        )


def test_training_service_rejects_arbitrary_python_command(tmp_path):
    service, _ = _service(tmp_path)

    with pytest.raises(ValueError):
        asyncio.run(service.execute_command(CommandRequest(command="python /tmp/malicious.py")))


def _wait_for_finish(service: TrainingService, training_id: str) -> None:
    import time

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = service.status(training_id)
        if status.state in {TrainingState.SUCCEEDED, TrainingState.FAILED, TrainingState.CANCELLED}:
            return
        time.sleep(0.05)
    raise AssertionError("Training run did not finish.")


def _service(root: Path):
    settings = Settings(
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
    )
    workspace = WorkspaceService(settings)
    workspace.ensure_workspace()
    file_service = FileService(settings, workspace)
    log_service = LogService(workspace)
    return TrainingService(settings, workspace, file_service, log_service), workspace
