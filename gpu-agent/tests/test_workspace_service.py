from pathlib import Path

import pytest

from app.config import Settings
from app.services.workspace_service import WorkspaceService


def test_workspace_creates_required_directories(tmp_path):
    service = WorkspaceService(_settings(tmp_path))

    service.ensure_workspace()

    assert (tmp_path / "dataset").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "artifacts").is_dir()


def test_workspace_rejects_path_traversal(tmp_path):
    service = WorkspaceService(_settings(tmp_path))
    service.ensure_workspace()

    with pytest.raises(ValueError):
        service.validate_path("../outside.txt")


def test_workspace_cleanup_deletes_temp_and_cache(tmp_path):
    service = WorkspaceService(_settings(tmp_path))
    service.ensure_workspace()
    (tmp_path / "temp" / "scratch.txt").write_text("abc", encoding="utf-8")
    (tmp_path / "cache" / "item.bin").write_text("12345", encoding="utf-8")

    deleted, bytes_deleted = service.cleanup_temp()

    assert bytes_deleted == 8
    assert sorted(deleted) == ["cache/item.bin", "temp/scratch.txt"]


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
    )
