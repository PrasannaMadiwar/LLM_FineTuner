from pathlib import Path

import pytest

from app.config import Settings
from app.services.file_service import FileService
from app.services.workspace_service import WorkspaceService


async def _chunks():
    yield b"hello"
    yield b" world"


async def _large_chunks():
    yield b"x" * 8
    yield b"y" * 8


def test_file_service_writes_stream(tmp_path):
    import asyncio

    workspace = WorkspaceService(_settings(tmp_path, max_upload_bytes=100))
    workspace.ensure_workspace()
    service = FileService(_settings(tmp_path, max_upload_bytes=100), workspace)

    path, bytes_written = asyncio.run(service.write_stream("dataset/train.txt", _chunks()))

    assert path.read_text(encoding="utf-8") == "hello world"
    assert bytes_written == 11


def test_file_service_enforces_upload_limit(tmp_path):
    import asyncio

    settings = _settings(tmp_path, max_upload_bytes=10)
    workspace = WorkspaceService(settings)
    workspace.ensure_workspace()
    service = FileService(settings, workspace)

    with pytest.raises(ValueError):
        asyncio.run(service.write_stream("dataset/train.txt", _large_chunks()))


def _settings(root: Path, max_upload_bytes: int) -> Settings:
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
        max_upload_bytes=max_upload_bytes,
        container_started_at=0,
    )
