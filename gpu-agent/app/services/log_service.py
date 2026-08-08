import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from app.models.schemas import LogEntry
from app.services.workspace_service import WorkspaceService


class LogService:
    def __init__(self, workspace_service: WorkspaceService):
        self._workspace_service = workspace_service

    def paths_for(self, training_id: str) -> tuple[Path, Path]:
        stdout_path = self._workspace_service.validate_path(f"logs/{training_id}.stdout.log")
        stderr_path = self._workspace_service.validate_path(f"logs/{training_id}.stderr.log")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        return stdout_path, stderr_path

    async def write_pipe(self, pipe: asyncio.StreamReader | None, path: Path) -> None:
        if pipe is None:
            return
        with path.open("ab") as file:
            while True:
                line = await pipe.readline()
                if not line:
                    break
                file.write(line)
                file.flush()

    def read_entries(self, training_id: str | None = None, limit: int = 500) -> list[LogEntry]:
        paths = self._paths(training_id)
        entries: list[LogEntry] = []
        for stream_name, path in paths:
            if not path.exists():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-limit:]:
                entries.append(
                    LogEntry(
                        stream=stream_name,
                        message=line,
                        timestamp=datetime.now(UTC),
                    )
                )
        return entries[-limit:]

    async def stream_entries(self, training_id: str | None = None) -> AsyncIterator[str]:
        for entry in self.read_entries(training_id):
            yield entry.model_dump_json() + "\n"

    def append_system_log(self, message: str) -> None:
        path = self._workspace_service.validate_path("logs/agent.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"timestamp": datetime.now(UTC).isoformat(), "message": message}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload) + "\n")

    def _paths(self, training_id: str | None) -> list[tuple[str, Path]]:
        if training_id:
            stdout_path, stderr_path = self.paths_for(training_id)
            return [("stdout", stdout_path), ("stderr", stderr_path)]
        log_root = self._workspace_service.validate_path("logs")
        if not log_root.exists():
            return []
        paths: list[tuple[str, Path]] = []
        for path in sorted(log_root.glob("*.stdout.log")):
            paths.append(("stdout", path))
        for path in sorted(log_root.glob("*.stderr.log")):
            paths.append(("stderr", path))
        agent_log = log_root / "agent.log"
        if agent_log.exists():
            paths.append(("stdout", agent_log))
        return paths
