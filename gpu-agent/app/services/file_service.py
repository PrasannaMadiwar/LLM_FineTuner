import time
from collections.abc import AsyncIterator
from pathlib import Path

from app.config import Settings
from app.services.workspace_service import WorkspaceService
from app.utils.paths import relative_to


class FileService:
    def __init__(self, settings: Settings, workspace_service: WorkspaceService):
        self._settings = settings
        self._workspace_service = workspace_service

    async def write_stream(self, remote_path: str, stream: AsyncIterator[bytes]) -> tuple[Path, int]:
        destination = self._workspace_service.validate_path(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0
        with destination.open("wb") as file:
            async for chunk in stream:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > self._settings.max_upload_bytes:
                    file.close()
                    destination.unlink(missing_ok=True)
                    raise ValueError("Upload exceeds the configured size limit.")
                file.write(chunk)
        return destination, bytes_written

    def file_metadata(self, remote_path: str) -> tuple[Path, int]:
        path = self._workspace_service.validate_path(remote_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("File does not exist.")
        return path, path.stat().st_size

    def list_artifacts(self, training_id: str) -> list[dict]:
        root = self._workspace_service.validate_path(f"artifacts/{training_id}")
        if not root.exists():
            return []
        artifacts = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            artifacts.append(
                {
                    "path": relative_to(self._workspace_service.workspace_path, path),
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )
        return artifacts

    def copy_to_artifact(self, source: Path, training_id: str, name: str | None = None) -> Path:
        destination = self._workspace_service.validate_path(
            f"artifacts/{training_id}/{name or source.name}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination

    @staticmethod
    def now_seconds() -> float:
        return time.monotonic()
