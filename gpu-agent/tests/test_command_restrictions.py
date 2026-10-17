import asyncio
import shutil
from pathlib import Path

import pytest

from app.config import Settings
from app.models.schemas import CommandRequest
from app.services.file_service import FileService
from app.services.log_service import LogService
from app.services.training_service import TrainingService
from app.services.workspace_service import WorkspaceService


@pytest.mark.parametrize("command", ["pip install requests", "pip --version", "pip3 install x", "python -m pip install x"])
def test_pip_is_not_allowed(tmp_path, command):
    service = _service(tmp_path)

    with pytest.raises(ValueError):
        _execute(service, command)


@pytest.mark.parametrize(
    "command",
    [
        "cp /etc/passwd outputs/passwd",
        "cp dataset/train.jsonl /tmp/exfil.jsonl",
        "cp dataset/train.jsonl ../outside.jsonl",
        "mv outputs ../../moved",
        "mv dataset/train.jsonl /etc/cron.d/job",
        "cp -t /etc dataset/train.jsonl",
        "cp --target-directory=/etc dataset/train.jsonl",
        "cp -- dataset/train.jsonl /tmp/x",
        "ls /",
        "ls ..",
        "mkdir /tmp/new-dir",
        "mkdir -p ../escape",
    ],
)
def test_path_arguments_outside_workspace_are_rejected(tmp_path, command):
    service = _service(tmp_path)

    with pytest.raises(ValueError):
        _execute(service, command)


def test_relative_paths_are_resolved_against_the_working_directory(tmp_path):
    service = _service(tmp_path)

    # From outputs/, "../dataset" is still inside the workspace but "../../x" is not.
    service._validate_path_arguments(["../dataset/train.jsonl", "copy.jsonl"], tmp_path / "outputs")
    with pytest.raises(ValueError):
        service._validate_path_arguments(["../../x"], tmp_path / "outputs")


@pytest.mark.parametrize(
    "arguments",
    [
        ["dataset/train.jsonl", "outputs/train.jsonl"],
        ["-r", "dataset", "outputs/dataset-copy"],
        ["-p", "outputs/a/b"],
        ["-la"],
        [],
    ],
)
def test_workspace_paths_and_short_flags_are_accepted(tmp_path, arguments):
    service = _service(tmp_path)

    service._validate_path_arguments(arguments, tmp_path)


@pytest.mark.skipif(shutil.which("cp") is None, reason="cp is not installed")
def test_cp_inside_workspace_runs(tmp_path):
    service = _service(tmp_path)
    (tmp_path / "dataset" / "train.jsonl").write_text("{}\n", encoding="utf-8")

    result = _execute(service, "cp dataset/train.jsonl outputs/train.jsonl")

    assert result.exit_code == 0
    assert (tmp_path / "outputs" / "train.jsonl").read_text(encoding="utf-8") == "{}\n"


@pytest.mark.skipif(shutil.which("cp") is None, reason="cp is not installed")
def test_symlink_pointing_outside_workspace_is_rejected(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    workspace = tmp_path / "ws"
    service = _service(workspace)
    link = workspace / "outputs" / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted here")

    with pytest.raises(ValueError):
        _execute(service, "cp dataset outputs/escape/copied")


@pytest.mark.parametrize("name", ["PATH", "path", "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "PYTHONPATH"])
def test_env_that_changes_what_runs_is_rejected(tmp_path, name):
    service = _service(tmp_path)

    with pytest.raises(ValueError, match="not allowed"):
        asyncio.run(
            service.execute_command(CommandRequest(command="ls outputs", env={name: str(tmp_path / "dataset")}))
        )


def _execute(service: TrainingService, command: str):
    return asyncio.run(service.execute_command(CommandRequest(command=command)))


def _service(root: Path) -> TrainingService:
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
        agent_token="test-token",
    )
    workspace = WorkspaceService(settings)
    workspace.ensure_workspace()
    return TrainingService(settings, workspace, FileService(settings, workspace), LogService(workspace))
