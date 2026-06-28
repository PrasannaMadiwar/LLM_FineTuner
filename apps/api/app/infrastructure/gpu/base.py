from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.gpu import (
    GPUCommand,
    GPUCommandResult,
    GPUCreateConfig,
    GPUDownloadResult,
    GPUHealthResult,
    GPULogEntry,
    GPUProviderError,
    GPUProviderInstance,
    GPUStatusResult,
    GPUUploadFile,
    GPUUploadResult,
)


class GPUProviderException(Exception):
    def __init__(self, error: GPUProviderError):
        super().__init__(error.message)
        self.error = error


class GPUProvider(ABC):
    @abstractmethod
    async def create_instance(self, config: GPUCreateConfig) -> GPUProviderInstance:
        raise NotImplementedError

    @abstractmethod
    async def terminate_instance(self, provider_instance_id: str) -> GPUStatusResult:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, provider_instance_id: str) -> GPUStatusResult:
        raise NotImplementedError

    @abstractmethod
    async def upload_files(
        self,
        provider_instance_id: str,
        files: list[GPUUploadFile],
    ) -> GPUUploadResult:
        raise NotImplementedError

    @abstractmethod
    async def download_files(
        self,
        provider_instance_id: str,
        remote_path: str,
    ) -> GPUDownloadResult:
        raise NotImplementedError

    @abstractmethod
    async def execute_command(
        self,
        provider_instance_id: str,
        command: GPUCommand,
    ) -> GPUCommandResult:
        raise NotImplementedError

    @abstractmethod
    async def stream_logs(self, provider_instance_id: str) -> AsyncIterator[GPULogEntry]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, provider_instance_id: str) -> GPUHealthResult:
        raise NotImplementedError

    @abstractmethod
    async def list_instances(self) -> list[GPUStatusResult]:
        raise NotImplementedError
