import asyncio
import json
import os
import re
import shlex
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from app.config import Settings
from app.models.schemas import (
    CommandRequest,
    CommandResponse,
    TrainingRecord,
    TrainingRequest,
    TrainingState,
    TrainingStatusResponse,
)
from app.services.file_service import FileService
from app.services.log_service import LogService
from app.services.workspace_service import WorkspaceService


class TrainingService:
    # pip is deliberately absent: installing packages runs arbitrary code, and the image
    # already ships every training dependency. Every argument of these commands must be
    # a short flag or a path inside the workspace.
    _ALLOWED_COMMANDS: ClassVar[set[str]] = {"mkdir", "cp", "mv", "ls"}
    _APPROVED_TEMPLATES: ClassVar[set[str]] = {"llama", "qwen", "gemma", "mistral"}
    _SHORT_FLAG: ClassVar[re.Pattern[str]] = re.compile(r"^-[A-Za-z0-9]+$")
    # Variables that change which binary or library runs would bypass the allowlist.
    _BLOCKED_ENV_PREFIXES: ClassVar[tuple[str, ...]] = ("LD_", "DYLD_", "PYTHON")
    _BLOCKED_ENV_NAMES: ClassVar[set[str]] = {"PATH"}

    def __init__(
        self,
        settings: Settings,
        workspace_service: WorkspaceService,
        file_service: FileService,
        log_service: LogService,
    ):
        self._settings = settings
        self._workspace_service = workspace_service
        self._file_service = file_service
        self._log_service = log_service
        self._records: dict[str, TrainingRecord] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    async def start_training(self, request: TrainingRequest) -> TrainingRecord:
        template_name = self._validate_template(request.template)
        dataset_path = self._workspace_service.validate_path(request.dataset_path)
        if not dataset_path.exists():
            raise FileNotFoundError("Dataset path does not exist.")

        training_id = str(uuid4())
        output_dir = self._workspace_service.validate_directory(
            request.output_dir or f"outputs/{training_id}"
        )
        artifact_dir = self._workspace_service.validate_directory(f"artifacts/{training_id}")
        config_path = self._workspace_service.validate_path(f"configs/{training_id}.json")
        stdout_path, stderr_path = self._log_service.paths_for(training_id)
        template_path = self._template_script(template_name)

        payload = {
            "training_id": training_id,
            "template": template_name,
            "dataset_path": str(dataset_path),
            "output_dir": str(output_dir),
            "artifact_dir": str(artifact_dir),
            "model": request.model,
            "config": request.config,
        }
        if request.resume_from_checkpoint:
            payload["config"]["resume_from_checkpoint"] = str(
                self._workspace_service.validate_path(request.resume_from_checkpoint)
            )
        config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        record = TrainingRecord(
            training_id=training_id,
            template=template_name,
            state=TrainingState.QUEUED,
            config_path=config_path,
            dataset_path=dataset_path,
            output_dir=output_dir,
            artifact_dir=artifact_dir,
            log_stdout_path=stdout_path,
            log_stderr_path=stderr_path,
        )
        self._records[training_id] = record
        asyncio.run_coroutine_threadsafe(self._run_training(record, template_path), self._loop)
        return record

    async def cancel_training(self, training_id: str) -> TrainingRecord:
        record = self._require_record(training_id)
        process = self._processes.get(training_id)
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        self._cleanup_runtime_files(record)
        updated = record.model_copy(
            update={
                "state": TrainingState.CANCELLED,
                "finished_at": datetime.now(UTC),
                "exit_code": process.returncode if process else record.exit_code,
            }
        )
        self._records[training_id] = updated
        return updated

    def status(self, training_id: str) -> TrainingStatusResponse:
        record = self._refresh_metrics(self._require_record(training_id))
        return TrainingStatusResponse(**record.model_dump())

    def artifacts(self, training_id: str) -> list[dict]:
        self._require_record(training_id)
        return self._file_service.list_artifacts(training_id)

    async def execute_command(self, payload: CommandRequest) -> CommandResponse:
        parts = shlex.split(payload.command, posix=True)
        if not parts:
            raise ValueError("Command cannot be empty.")
        executable = parts[0]
        self._validate_env(payload.env)
        working_directory = (
            self._workspace_service.validate_path(payload.working_directory)
            if payload.working_directory
            else self._workspace_service.workspace_path
        )
        if executable == "python":
            self._validate_python_command(parts)
        elif executable in self._ALLOWED_COMMANDS:
            self._validate_path_arguments(parts[1:], working_directory)
        else:
            raise ValueError("Command is not approved for runtime execution.")

        if not working_directory.is_dir():
            raise ValueError("Working directory does not exist.")

        env = {**os.environ, **payload.env}
        started_at = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *parts,
            cwd=working_directory,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=payload.timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError("Command timed out.") from None
        return CommandResponse(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=process.returncode or 0,
            execution_time_seconds=time.monotonic() - started_at,
        )

    def _validate_path_arguments(self, arguments: list[str], working_directory: Path) -> None:
        for argument in arguments:
            if argument.startswith("-"):
                # Long options such as --target-directory=/etc can smuggle in a path.
                if not self._SHORT_FLAG.match(argument):
                    raise ValueError(f"Option '{argument}' is not allowed; use short flags only.")
                continue
            path = Path(argument)
            candidate = path if path.is_absolute() else working_directory / path
            try:
                self._workspace_service.validate_path(candidate)
            except ValueError as exc:
                raise ValueError(f"Path '{argument}' is outside the workspace.") from exc

    def _validate_env(self, env: dict[str, str]) -> None:
        for name in env:
            upper = name.upper()
            if upper in self._BLOCKED_ENV_NAMES or upper.startswith(self._BLOCKED_ENV_PREFIXES):
                raise ValueError(f"Environment variable '{name}' is not allowed for runtime commands.")

    def _validate_template(self, template: str) -> str:
        normalized = template.lower().strip()
        if normalized not in self._APPROVED_TEMPLATES:
            raise ValueError("Training template is not approved.")
        return normalized

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _template_script(self, template: str) -> Path:
        source = Path(__file__).resolve().parents[2] / "templates" / template / "train.py"
        if not source.exists():
            source = self._settings.template_path / template / "train.py"
        if not source.exists():
            raise FileNotFoundError(f"Template '{template}' is not installed.")
        return source

    async def _run_training(self, record: TrainingRecord, template_path: Path) -> None:
        started = datetime.now(UTC)
        running = record.model_copy(update={"state": TrainingState.RUNNING, "started_at": started})
        self._records[record.training_id] = running
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(template_path),
            "--config",
            str(record.config_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._workspace_service.workspace_path,
        )
        self._processes[record.training_id] = process
        running = running.model_copy(update={"process_id": process.pid})
        self._records[record.training_id] = running
        await asyncio.gather(
            self._log_service.write_pipe(process.stdout, record.log_stdout_path),
            self._log_service.write_pipe(process.stderr, record.log_stderr_path),
        )
        exit_code = await process.wait()
        final_state = TrainingState.SUCCEEDED if exit_code == 0 else TrainingState.FAILED
        if final_state == TrainingState.FAILED:
            self._cleanup_runtime_files(running)
        finished = running.model_copy(
            update={
                "state": final_state,
                "exit_code": exit_code,
                "finished_at": datetime.now(UTC),
                "error": None if exit_code == 0 else "Training process failed.",
            }
        )
        self._records[record.training_id] = self._refresh_metrics(finished)

    def _refresh_metrics(self, record: TrainingRecord) -> TrainingRecord:
        # Pure read: status requests run on another thread than the training loop, so
        # storing here could overwrite a state change (e.g. RUNNING -> SUCCEEDED).
        metrics_path = record.output_dir / "metrics.json"
        metrics_payload = {}
        if not metrics_path.exists():
            payload = {}
        else:
            try:
                payload = json.loads(metrics_path.read_text(encoding="utf-8"))
                metrics_payload = payload
            except json.JSONDecodeError:
                payload = {}
        updated = record.model_copy(
            update={
                "current_epoch": payload.get("current_epoch"),
                "loss": payload.get("loss"),
                "learning_rate": payload.get("learning_rate"),
                "eta_seconds": payload.get("eta_seconds"),
                "global_step": payload.get("global_step"),
                "metrics": metrics_payload,
                "checkpoints": self._list_checkpoints(record),
            }
        )
        return updated

    def _list_checkpoints(self, record: TrainingRecord) -> list[str]:
        checkpoint_root = record.artifact_dir / "checkpoints"
        if not checkpoint_root.exists():
            checkpoint_root = record.output_dir / "checkpoints"
        if not checkpoint_root.exists():
            return []
        return [
            str(path.relative_to(self._workspace_service.workspace_path))
            for path in sorted(checkpoint_root.glob("checkpoint-*"))
            if path.is_dir()
        ]

    def _cleanup_runtime_files(self, record: TrainingRecord) -> None:
        for path in [record.config_path]:
            path.unlink(missing_ok=True)
        temp_dir = self._workspace_service.validate_path(f"temp/{record.training_id}")
        if temp_dir.exists():
            import shutil

            shutil.rmtree(temp_dir)

    def _require_record(self, training_id: str) -> TrainingRecord:
        record = self._records.get(training_id)
        if record is None:
            raise KeyError("Training run was not found.")
        return record

    def _validate_python_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            raise ValueError("Python command must target an approved template.")
        script = Path(parts[1])
        template_root = Path(__file__).resolve().parents[2] / "templates"
        candidate = script.resolve() if script.is_absolute() else (
            self._workspace_service.workspace_path / script
        ).resolve()
        if template_root not in candidate.parents and self._settings.template_path not in candidate.parents:
            raise ValueError("Python commands may only execute approved training templates.")
