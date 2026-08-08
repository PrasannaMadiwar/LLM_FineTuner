import shutil
from pathlib import Path

from app.config import Settings
from app.utils.paths import relative_to, resolve_under


class WorkspaceService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._workspace = settings.workspace_path
        self._managed_paths = [
            settings.dataset_path,
            settings.config_path,
            settings.template_path,
            settings.output_path,
            settings.checkpoint_path,
            settings.log_path,
            settings.artifact_path,
            settings.cache_path,
            settings.temp_path,
        ]

    @property
    def workspace_path(self) -> Path:
        return self._workspace

    def ensure_workspace(self) -> None:
        self._workspace.mkdir(parents=True, exist_ok=True)
        for path in self._managed_paths:
            self._ensure_managed_path(path)
            path.mkdir(parents=True, exist_ok=True)

    def validate_path(self, requested_path: str | Path) -> Path:
        return resolve_under(self._workspace, requested_path)

    def validate_directory(self, requested_path: str | Path) -> Path:
        path = self.validate_path(requested_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def disk_usage(self) -> dict:
        usage = shutil.disk_usage(self._workspace)
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }

    def workspace_size_bytes(self) -> int:
        total = 0
        if not self._workspace.exists():
            return total
        for path in self._workspace.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def cleanup_temp(self) -> tuple[list[str], int]:
        deleted_paths: list[str] = []
        bytes_deleted = 0
        for root in [self._settings.temp_path, self._settings.cache_path]:
            self._ensure_managed_path(root)
            if not root.exists():
                continue
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file():
                    size = path.stat().st_size
                    path.unlink()
                    bytes_deleted += size
                    deleted_paths.append(relative_to(self._workspace, path))
                elif path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
            root.mkdir(parents=True, exist_ok=True)
        return deleted_paths, bytes_deleted

    def _ensure_managed_path(self, path: Path) -> None:
        resolved = path.resolve()
        workspace = self._workspace.resolve()
        if resolved != workspace and workspace not in resolved.parents:
            raise ValueError(f"Configured path '{path}' is outside the workspace.")
