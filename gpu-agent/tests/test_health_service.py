from pathlib import Path

from app.config import Settings
from app.services.health_service import HealthService
from app.services.workspace_service import WorkspaceService


def test_health_service_returns_structured_health(tmp_path):
    settings = _settings(tmp_path)
    workspace = WorkspaceService(settings)
    workspace.ensure_workspace()
    service = HealthService(settings, workspace)

    health = service.get_health()

    assert health.status == "ok"
    assert health.disk["total_bytes"] > 0
    assert health.workspace_size_bytes >= 0


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
