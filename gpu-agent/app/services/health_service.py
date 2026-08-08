import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from app.config import Settings
from app.models.schemas import HealthResponse
from app.services.workspace_service import WorkspaceService


class HealthService:
    def __init__(self, settings: Settings, workspace_service: WorkspaceService):
        self._settings = settings
        self._workspace_service = workspace_service

    def get_health(self) -> HealthResponse:
        disk = self._workspace_service.disk_usage()
        ram = self._memory_info()
        gpu = self._gpu_info()
        return HealthResponse(
            status="ok",
            gpu_status="available" if gpu else "unavailable",
            disk=disk,
            ram=ram,
            vram=gpu.get("vram") if gpu else None,
            cuda_version=gpu.get("cuda_version") if gpu else self._cuda_version(),
            torch_version=self._torch_version(),
            installed_models=self._installed_models(),
            workspace_size_bytes=self._workspace_service.workspace_size_bytes(),
            container_uptime_seconds=max(0.0, time.time() - self._settings.container_started_at)
            if self._settings.container_started_at
            else 0.0,
        )

    @staticmethod
    def _memory_info() -> dict:
        meminfo = Path("/proc/meminfo")
        if not meminfo.exists():
            return {"total_bytes": None, "available_bytes": None}
        values = {}
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) * 1024
        return {
            "total_bytes": values.get("MemTotal"),
            "available_bytes": values.get("MemAvailable"),
        }

    @staticmethod
    def _gpu_info() -> dict:
        nvidia_smi = shutil.which("nvidia-smi")
        if not nvidia_smi:
            return {}
        try:
            result = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return {}
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        first = result.stdout.strip().splitlines()[0]
        name, total, used, utilization = [item.strip() for item in first.split(",")]
        return {
            "name": name,
            "vram": {
                "total_mb": int(total),
                "used_mb": int(used),
                "utilization_percent": float(utilization),
            },
            "cuda_version": HealthService._cuda_version(),
        }

    @staticmethod
    def _cuda_version() -> str | None:
        version_file = Path("/usr/local/cuda/version.json")
        if version_file.exists():
            try:
                payload = json.loads(version_file.read_text(encoding="utf-8"))
                return str(payload.get("cuda", {}).get("version")) if payload.get("cuda") else None
            except json.JSONDecodeError:
                return None
        return os.environ.get("CUDA_VERSION")

    @staticmethod
    def _torch_version() -> str | None:
        try:
            import torch
        except Exception:
            return None
        return str(torch.__version__)

    def _installed_models(self) -> list[str]:
        model_root = self._workspace_service.validate_path("cache/models")
        if not model_root.exists():
            return []
        return sorted(path.name for path in model_root.iterdir() if path.is_dir())
