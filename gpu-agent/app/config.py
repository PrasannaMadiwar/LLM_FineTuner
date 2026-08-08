import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    workspace_path: Path
    dataset_path: Path
    config_path: Path
    template_path: Path
    output_path: Path
    checkpoint_path: Path
    log_path: Path
    artifact_path: Path
    cache_path: Path
    temp_path: Path
    port: int
    max_upload_bytes: int
    container_started_at: float
    agent_token: str | None = None


_STARTED_AT = float(os.environ.get("CONTAINER_STARTED_AT", str(time.time())) or str(time.time()))


def get_settings() -> Settings:
    workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace")).resolve()
    return Settings(
        workspace_path=workspace,
        dataset_path=Path(os.environ.get("DATASET_PATH", workspace / "dataset")).resolve(),
        config_path=Path(os.environ.get("CONFIG_PATH", workspace / "configs")).resolve(),
        template_path=Path(os.environ.get("TEMPLATE_PATH", workspace / "templates")).resolve(),
        output_path=Path(os.environ.get("OUTPUT_PATH", workspace / "outputs")).resolve(),
        checkpoint_path=Path(os.environ.get("CHECKPOINT_PATH", workspace / "checkpoints")).resolve(),
        log_path=Path(os.environ.get("LOG_PATH", workspace / "logs")).resolve(),
        artifact_path=Path(os.environ.get("ARTIFACT_PATH", workspace / "artifacts")).resolve(),
        cache_path=Path(os.environ.get("CACHE_PATH", workspace / "cache")).resolve(),
        temp_path=Path(os.environ.get("TEMP_PATH", workspace / "temp")).resolve(),
        port=int(os.environ.get("PORT", "8001")),
        max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024 * 1024))),
        container_started_at=_STARTED_AT,
        agent_token=os.environ.get("GPU_AGENT_TOKEN"),
    )
