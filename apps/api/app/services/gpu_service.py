from collections.abc import AsyncIterator
from datetime import UTC, datetime
import asyncio
import logging
import shlex
from uuid import UUID

from app.core.config import get_settings
from app.domain.gpu import (
    GPUCommand,
    GPUCommandResult,
    GPUCreateConfig,
    GPUErrorCode,
    GPUEventType,
    GPUHealthResult,
    GPUInstance,
    GPUInstanceStatus,
    GPULogEntry,
    GPUProviderError,
    GPUProviderName,
    GPUStatusResult,
    GPUUploadFile,
    GPUUploadResult,
)
from app.infrastructure.gpu.base import GPUProvider, GPUProviderException
from app.infrastructure.repositories.gpu_repository import GPURepository

logger = logging.getLogger(__name__)


class GPUService:
    # Mirrors the GPU agent allowlist (no pip); the agent also confines paths to its workspace.
    _ALLOWED_COMMANDS = {"python", "mkdir", "cp", "mv", "ls"}

    def __init__(
        self,
        repository: GPURepository,
        provider: GPUProvider,
        provider_name: GPUProviderName = GPUProviderName.RUNPOD,
        create_timeout_seconds: int | None = None,
        operation_max_retries: int | None = None,
        poll_interval_seconds: float = 5.0,
    ):
        settings = get_settings()
        self._repository = repository
        self._provider = provider
        self._provider_name = provider_name
        self._create_timeout_seconds = (
            create_timeout_seconds
            if create_timeout_seconds is not None
            else settings.gpu_create_timeout_seconds
        )
        self._operation_max_retries = (
            operation_max_retries
            if operation_max_retries is not None
            else settings.gpu_operation_max_retries
        )
        self._poll_interval_seconds = poll_interval_seconds

    async def create_instance(
        self,
        user_id: UUID,
        config: GPUCreateConfig,
        project_id: UUID | None = None,
    ) -> GPUInstance:
        instance = await self._repository.create_instance(
            user_id=user_id,
            provider=self._provider_name,
            status=GPUInstanceStatus.PENDING,
            project_id=project_id,
            gpu_type=config.gpu_type,
            metadata=config.metadata,
        )
        await self._record_event(
            user_id,
            GPUEventType.INSTANCE_CREATE_REQUESTED,
            "GPU creation requested.",
            instance.id,
            {"gpu_type": config.gpu_type},
        )
        provider_instance_id: str | None = None
        try:
            provider_instance = await self._with_retries(
                lambda: self._provider.create_instance(config),
                user_id,
                instance.id,
                "create GPU instance",
            )
            provider_instance_id = provider_instance.provider_instance_id
            instance = await self._repository.update_instance(
                instance.id,
                status=provider_instance.status,
                provider_instance_id=provider_instance.provider_instance_id,
                endpoint_url=provider_instance.endpoint_url,
                metadata=provider_instance.metadata,
            )
            await self._record_event(
                user_id,
                GPUEventType.INSTANCE_CREATED,
                "GPU provider instance created.",
                instance.id,
                {"provider_instance_id": provider_instance.provider_instance_id},
            )
            ready_status = await self._wait_until_ready(provider_instance.provider_instance_id)
            instance = await self._repository.update_instance(
                instance.id,
                status=ready_status.status,
                endpoint_url=ready_status.endpoint_url,
                metadata=ready_status.metadata,
            )
            health = await self._provider.health_check(provider_instance.provider_instance_id)
            await self._record_event(
                user_id,
                GPUEventType.INSTANCE_HEALTH_CHECKED,
                "GPU health check completed.",
                instance.id,
                health.model_dump(mode="json"),
            )
            if not health.healthy:
                raise GPUProviderException(
                    GPUProviderError(
                        code=GPUErrorCode.GPU_UNAVAILABLE,
                        message=health.message or "GPU failed health check.",
                        retryable=True,
                    )
                )
            await self._record_event(
                user_id,
                GPUEventType.INSTANCE_READY,
                "GPU instance is ready.",
                instance.id,
            )
            return instance
        except Exception:
            await self._repository.update_instance(instance.id, status=GPUInstanceStatus.FAILED)
            await self._record_event(
                user_id,
                GPUEventType.ERROR,
                "GPU creation failed.",
                instance.id,
            )
            if provider_instance_id:
                await self._cleanup_provider_instance(provider_instance_id, user_id, instance.id)
            raise

    async def terminate_instance(self, user_id: UUID, instance_id: UUID) -> GPUInstance:
        instance = await self._require_owned_instance(user_id, instance_id)
        if instance.provider_instance_id is None:
            return await self._repository.update_instance(
                instance.id,
                status=GPUInstanceStatus.STOPPED,
                terminated_at=datetime.now(UTC),
            )
        await self._record_event(
            user_id,
            GPUEventType.INSTANCE_TERMINATE_REQUESTED,
            "GPU termination requested.",
            instance.id,
        )
        await self._repository.update_instance(instance.id, status=GPUInstanceStatus.STOPPING)
        status = await self._with_retries(
            lambda: self._provider.terminate_instance(instance.provider_instance_id or ""),
            user_id,
            instance.id,
            "terminate GPU instance",
        )
        updated = await self._repository.update_instance(
            instance.id,
            status=status.status,
            metadata=status.metadata,
            terminated_at=datetime.now(UTC),
        )
        await self._record_event(
            user_id,
            GPUEventType.INSTANCE_TERMINATED,
            "GPU termination completed.",
            instance.id,
        )
        return updated

    async def get_instance(self, user_id: UUID, instance_id: UUID, refresh: bool = True) -> GPUInstance:
        instance = await self._require_owned_instance(user_id, instance_id)
        if refresh and instance.provider_instance_id:
            status = await self._provider.get_status(instance.provider_instance_id)
            instance = await self._repository.update_instance(
                instance.id,
                status=status.status,
                endpoint_url=status.endpoint_url,
                metadata=status.metadata,
            )
        return instance

    async def list_instances(self, user_id: UUID) -> list[GPUInstance]:
        return await self._repository.list_instances(user_id)

    async def execute_command(
        self,
        user_id: UUID,
        instance_id: UUID,
        command: GPUCommand,
    ) -> GPUCommandResult:
        self._validate_command(command.command)
        instance = await self._require_provider_instance(user_id, instance_id)
        await self._record_event(
            user_id,
            GPUEventType.COMMAND_STARTED,
            "Remote command started.",
            instance.id,
            {"command": self._redact_command(command.command)},
        )
        result = await self._with_retries(
            lambda: self._provider.execute_command(instance.provider_instance_id or "", command),
            user_id,
            instance.id,
            "execute remote command",
        )
        await self._record_event(
            user_id,
            GPUEventType.COMMAND_COMPLETED,
            "Remote command completed.",
            instance.id,
            {"exit_code": result.exit_code, "execution_time_seconds": result.execution_time_seconds},
        )
        return result

    async def upload_files(
        self,
        user_id: UUID,
        instance_id: UUID,
        files: list[GPUUploadFile],
    ) -> GPUUploadResult:
        instance = await self._require_provider_instance(user_id, instance_id)
        await self._record_event(
            user_id,
            GPUEventType.FILE_UPLOAD_STARTED,
            "GPU file upload started.",
            instance.id,
            {"files": [file.remote_path for file in files]},
        )
        result = await self._with_retries(
            lambda: self._provider.upload_files(instance.provider_instance_id or "", files),
            user_id,
            instance.id,
            "upload GPU files",
        )
        await self._record_event(
            user_id,
            GPUEventType.FILE_UPLOAD_COMPLETED,
            "GPU file upload completed.",
            instance.id,
            result.model_dump(mode="json"),
        )
        return result

    async def health_check(self, user_id: UUID, instance_id: UUID) -> GPUHealthResult:
        instance = await self._require_provider_instance(user_id, instance_id)
        health = await self._provider.health_check(instance.provider_instance_id or "")
        await self._record_event(
            user_id,
            GPUEventType.INSTANCE_HEALTH_CHECKED,
            "GPU health check completed.",
            instance.id,
            health.model_dump(mode="json"),
        )
        return health

    async def stream_logs(self, user_id: UUID, instance_id: UUID) -> AsyncIterator[GPULogEntry]:
        instance = await self._require_provider_instance(user_id, instance_id)
        await self._record_event(
            user_id,
            GPUEventType.LOGS_REQUESTED,
            "GPU logs requested.",
            instance.id,
        )
        async for entry in self._provider.stream_logs(instance.provider_instance_id or ""):
            yield entry

    async def _wait_until_ready(self, provider_instance_id: str) -> GPUStatusResult:
        deadline = asyncio.get_running_loop().time() + self._create_timeout_seconds
        last_status: GPUStatusResult | None = None
        while asyncio.get_running_loop().time() <= deadline:
            last_status = await self._provider.get_status(provider_instance_id)
            if last_status.status == GPUInstanceStatus.RUNNING:
                return last_status
            if last_status.status in {GPUInstanceStatus.FAILED, GPUInstanceStatus.UNAVAILABLE}:
                raise GPUProviderException(
                    GPUProviderError(
                        code=GPUErrorCode.GPU_UNAVAILABLE,
                        message=f"GPU entered {last_status.status.value} state.",
                        retryable=False,
                    )
                )
            await asyncio.sleep(self._poll_interval_seconds)
        raise GPUProviderException(
            GPUProviderError(
                code=GPUErrorCode.TIMEOUT,
                message="Timed out waiting for GPU to become ready.",
                retryable=True,
                status_code=None,
            )
        )

    async def _with_retries(self, operation, user_id: UUID, instance_id: UUID | None, action: str):
        last_error: GPUProviderException | None = None
        for attempt in range(self._operation_max_retries + 1):
            try:
                return await operation()
            except GPUProviderException as exc:
                last_error = exc
                if not exc.error.retryable or attempt >= self._operation_max_retries:
                    logger.exception("GPU provider failed to %s.", action)
                    await self._record_event(
                        user_id,
                        GPUEventType.ERROR,
                        f"Failed to {action}.",
                        instance_id,
                        exc.error.model_dump(mode="json"),
                    )
                    raise
                await self._record_event(
                    user_id,
                    GPUEventType.RETRY,
                    f"Retrying to {action}.",
                    instance_id,
                    {"attempt": attempt + 1, "error": exc.error.model_dump(mode="json")},
                )
                await asyncio.sleep(2**attempt * 0.5)
        if last_error:
            raise last_error
        raise RuntimeError(f"Failed to {action}.")

    async def _require_owned_instance(self, user_id: UUID, instance_id: UUID) -> GPUInstance:
        instance = await self._repository.get_instance(instance_id)
        if instance is None:
            raise ValueError("GPU instance not found.")
        if instance.user_id != user_id:
            raise PermissionError("You do not have access to this GPU instance.")
        return instance

    async def _require_provider_instance(self, user_id: UUID, instance_id: UUID) -> GPUInstance:
        instance = await self._require_owned_instance(user_id, instance_id)
        if not instance.provider_instance_id:
            raise ValueError("GPU provider instance is not available.")
        return instance

    async def _cleanup_provider_instance(
        self,
        provider_instance_id: str,
        user_id: UUID,
        instance_id: UUID,
    ) -> None:
        try:
            await self._provider.terminate_instance(provider_instance_id)
        except GPUProviderException as exc:
            await self._record_event(
                user_id,
                GPUEventType.ERROR,
                "Automatic GPU cleanup failed.",
                instance_id,
                exc.error.model_dump(mode="json"),
            )

    async def _record_event(
        self,
        user_id: UUID,
        event_type: GPUEventType,
        message: str,
        instance_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        await self._repository.add_event(
            user_id=user_id,
            event_type=event_type,
            message=message,
            gpu_instance_id=instance_id,
            metadata=metadata,
        )

    def _validate_command(self, command: str) -> None:
        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            raise ValueError("Command could not be parsed.") from exc
        if not parts:
            raise ValueError("Command cannot be empty.")
        executable = parts[0].lower()
        if executable not in self._ALLOWED_COMMANDS:
            raise ValueError("Command is not allowed for GPU remote execution.")

    @staticmethod
    def _redact_command(command: str) -> str:
        redacted_parts: list[str] = []
        for part in command.split():
            if any(token in part.lower() for token in ("key=", "token=", "secret=", "password=")):
                redacted_parts.append("[REDACTED]")
            else:
                redacted_parts.append(part)
        return " ".join(redacted_parts)
