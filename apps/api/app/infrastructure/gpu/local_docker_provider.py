import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.domain.gpu import (
    GPUCommand,
    GPUCommandResult,
    GPUCreateConfig,
    GPUDownloadResult,
    GPUErrorCode,
    GPUHealthResult,
    GPUInstanceStatus,
    GPULogEntry,
    GPUProviderError,
    GPUProviderInstance,
    GPUStatusResult,
    GPUUploadFile,
    GPUUploadResult,
)
from app.infrastructure.gpu.base import GPUProvider, GPUProviderException

MANAGED_LABEL = "llm-finetuner.managed"


class LocalDockerProvider(GPUProvider):
    """Runs the GPU agent image as a container on the local GPU.

    It plays the same role a cloud provider does: "creating an instance" starts a
    container from the agent image and "terminating" removes it, so the training
    orchestrator runs the identical pipeline against a local GPU.
    """

    def __init__(
        self,
        socket_path: str | None = None,
        image: str | None = None,
        network: str | None = None,
        workspace_volume: str | None = None,
        hf_cache_volume: str | None = None,
        agent_port: int | None = None,
        agent_token: str | None = None,
        timeout_seconds: float = 30.0,
        docker_transport: httpx.AsyncBaseTransport | None = None,
        agent_transport: httpx.AsyncBaseTransport | None = None,
    ):
        settings = get_settings()
        self._socket_path = socket_path or settings.docker_socket_path
        self._image = image or settings.local_gpu_image
        self._network = network or settings.local_gpu_network
        self._workspace_volume = workspace_volume or settings.local_gpu_workspace_volume
        self._hf_cache_volume = hf_cache_volume or settings.local_gpu_hf_cache_volume
        self._agent_port = agent_port or settings.local_gpu_agent_port
        self._agent_token = agent_token if agent_token is not None else settings.gpu_agent_token
        self._timeout_seconds = timeout_seconds
        self._docker_transport = docker_transport
        self._agent_transport = agent_transport

    async def create_instance(self, config: GPUCreateConfig) -> GPUProviderInstance:
        if not self._agent_token:
            raise self._provider_error(
                GPUErrorCode.MISSING_API_KEY,
                "GPU_AGENT_TOKEN must be set so the local GPU agent does not run unauthenticated.",
            )
        await self._ensure_gpu_is_free()

        image = config.image or self._image
        container_name = f"llm-finetuner-gpu-{uuid4().hex[:12]}"
        env = {**config.env, "GPU_AGENT_TOKEN": self._agent_token, "PORT": str(self._agent_port)}
        body = {
            "Image": image,
            "Env": [f"{key}={value}" for key, value in env.items()],
            "Labels": {MANAGED_LABEL: "true", "llm-finetuner.instance-name": config.name},
            "ExposedPorts": {f"{self._agent_port}/tcp": {}},
            "HostConfig": {
                "DeviceRequests": [{"Driver": "nvidia", "Count": -1, "Capabilities": [["gpu"]]}],
                "NetworkMode": self._network,
                "Mounts": [
                    {"Type": "volume", "Source": self._workspace_volume, "Target": "/workspace"},
                    {"Type": "volume", "Source": self._hf_cache_volume, "Target": "/opt/hf-cache"},
                ],
                # Dataset preprocessing workers share memory; Docker's 64 MB default is too small.
                "ShmSize": 2 * 1024 * 1024 * 1024,
            },
        }
        created = await self._docker(
            "POST",
            "/containers/create",
            params={"name": container_name},
            json_payload=body,
            not_found_message=(
                f"GPU agent image '{image}' was not found. "
                f"Build it with: docker build -t {image} gpu-agent"
            ),
        )
        container_id = str(created["Id"])
        try:
            await self._docker("POST", f"/containers/{container_id}/start")
        except GPUProviderException:
            await self._docker("DELETE", f"/containers/{container_id}", params={"force": "true"}, allowed={404})
            raise
        return GPUProviderInstance(
            provider_instance_id=container_id,
            status=GPUInstanceStatus.STARTING,
            endpoint_url=self._endpoint(container_name),
            metadata={"container_name": container_name, "image": image},
        )

    async def terminate_instance(self, provider_instance_id: str) -> GPUStatusResult:
        await self._docker(
            "POST",
            f"/containers/{provider_instance_id}/stop",
            params={"t": "15"},
            allowed={304, 404},
        )
        await self._docker(
            "DELETE",
            f"/containers/{provider_instance_id}",
            params={"force": "true"},
            allowed={404},
        )
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=GPUInstanceStatus.STOPPED,
            message="Local GPU container removed.",
        )

    async def get_status(self, provider_instance_id: str) -> GPUStatusResult:
        payload = await self._docker("GET", f"/containers/{provider_instance_id}/json", allowed={404})
        if not payload:
            return GPUStatusResult(
                provider_instance_id=provider_instance_id,
                status=GPUInstanceStatus.STOPPED,
                message="Local GPU container no longer exists.",
            )
        state = payload.get("State") or {}
        endpoint_url = self._endpoint(str(payload.get("Name") or "").lstrip("/"))
        status = self._map_status(state)
        # A running container is not usable until the agent inside it answers.
        if status == GPUInstanceStatus.RUNNING and not await self._agent_is_ready(endpoint_url):
            status = GPUInstanceStatus.STARTING
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=status,
            message=state.get("Error") or None,
            endpoint_url=endpoint_url,
            metadata={"state": state.get("Status"), "exit_code": state.get("ExitCode")},
        )

    async def upload_files(
        self,
        provider_instance_id: str,
        files: list[GPUUploadFile],
    ) -> GPUUploadResult:
        started_at = time.monotonic()
        uploaded_files: list[str] = []
        bytes_uploaded = 0
        for file in files:
            response_payload = await self._agent_request(
                provider_instance_id,
                "PUT",
                "/files",
                params={"path": file.remote_path},
                content=file.stream,
                headers={"Content-Type": file.content_type or "application/octet-stream"},
            )
            bytes_uploaded += int(response_payload.get("bytes_uploaded") or 0)
            uploaded_files.append(file.remote_path)
        return GPUUploadResult(
            files=uploaded_files,
            bytes_uploaded=bytes_uploaded,
            duration_seconds=time.monotonic() - started_at,
        )

    async def download_files(self, provider_instance_id: str, remote_path: str) -> GPUDownloadResult:
        response_payload = await self._agent_request(
            provider_instance_id,
            "GET",
            "/files",
            params={"path": remote_path},
        )
        return GPUDownloadResult(
            remote_path=remote_path,
            bytes_downloaded=int(response_payload.get("bytes_downloaded") or 0),
        )

    async def execute_command(self, provider_instance_id: str, command: GPUCommand) -> GPUCommandResult:
        response_payload = await self._agent_request(
            provider_instance_id,
            "POST",
            "/commands",
            json_payload={
                "command": command.command,
                "timeout_seconds": command.timeout_seconds,
                "working_directory": command.working_directory,
                "env": command.env,
            },
            timeout_seconds=command.timeout_seconds,
        )
        return GPUCommandResult(
            stdout=str(response_payload.get("stdout") or ""),
            stderr=str(response_payload.get("stderr") or ""),
            exit_code=int(response_payload.get("exit_code") or 0),
            execution_time_seconds=float(response_payload.get("execution_time_seconds") or 0.0),
        )

    async def stream_logs(self, provider_instance_id: str) -> AsyncIterator[GPULogEntry]:
        agent_url = await self._resolve_agent_url(provider_instance_id)
        async with httpx.AsyncClient(timeout=None, transport=self._agent_transport) as client:
            async with client.stream("GET", f"{agent_url}/logs", headers=self._agent_headers()) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise self._http_error(response, "GPU agent")
                async for line in response.aiter_lines():
                    if line:
                        yield self._parse_log_line(line)

    async def health_check(self, provider_instance_id: str) -> GPUHealthResult:
        try:
            status = await self.get_status(provider_instance_id)
            response_payload = await self._agent_request(provider_instance_id, "GET", "/health")
        except GPUProviderException as exc:
            return GPUHealthResult(
                healthy=False,
                status=GPUInstanceStatus.UNAVAILABLE,
                message=exc.error.message,
                details=exc.error.model_dump(mode="json"),
            )
        return GPUHealthResult(
            healthy=status.status == GPUInstanceStatus.RUNNING,
            status=status.status,
            message="Local GPU agent is healthy.",
            details=response_payload,
        )

    async def list_instances(self) -> list[GPUStatusResult]:
        containers = await self._docker(
            "GET",
            "/containers/json",
            params={"all": "true", "filters": json.dumps({"label": [f"{MANAGED_LABEL}=true"]})},
        )
        return [
            GPUStatusResult(
                provider_instance_id=str(container["Id"]),
                status=self._map_status({"Status": container.get("State")}),
                endpoint_url=self._endpoint(str((container.get("Names") or ["/"])[0]).lstrip("/")),
                metadata={"image": container.get("Image"), "state": container.get("State")},
            )
            for container in containers
        ]

    async def _ensure_gpu_is_free(self) -> None:
        # A laptop GPU cannot fit two training runs, so the local provider hands out
        # one GPU container at a time instead of letting the second job run out of memory.
        running = await self._docker(
            "GET",
            "/containers/json",
            params={"filters": json.dumps({"label": [f"{MANAGED_LABEL}=true"]})},
        )
        if running:
            names = ", ".join(str((item.get("Names") or ["?"])[0]).lstrip("/") for item in running)
            raise self._provider_error(
                GPUErrorCode.GPU_UNAVAILABLE,
                f"The local GPU is already in use by {names}. Wait for that job to finish "
                "or remove the container with 'docker rm -f <name>'.",
            )

    async def _docker(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_payload: dict | None = None,
        allowed: set[int] | frozenset[int] = frozenset(),
        not_found_message: str | None = None,
    ) -> Any:
        transport = self._docker_transport or httpx.AsyncHTTPTransport(uds=self._socket_path)
        try:
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://docker",
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.request(method, path, params=params, json=json_payload)
        except httpx.HTTPError as exc:
            raise self._provider_error(
                GPUErrorCode.NETWORK_ERROR,
                f"Could not reach the Docker daemon at {self._socket_path}. "
                "Is Docker running and the socket mounted into this container?",
            ) from exc
        if response.status_code in allowed:
            return {}
        if response.status_code == 404 and not_found_message:
            raise self._provider_error(GPUErrorCode.NOT_FOUND, not_found_message, status_code=404)
        if response.status_code >= 400:
            raise self._http_error(response, "Docker")
        return response.json() if response.content else {}

    async def _agent_request(
        self,
        provider_instance_id: str,
        method: str,
        path: str,
        params: dict | None = None,
        json_payload: dict | None = None,
        content: AsyncIterator[bytes] | None = None,
        headers: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict:
        agent_url = await self._resolve_agent_url(provider_instance_id)
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds or self._timeout_seconds,
                transport=self._agent_transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{agent_url}{path}",
                    params=params,
                    json=json_payload,
                    content=content,
                    headers={**self._agent_headers(), **(headers or {})},
                )
        except httpx.TimeoutException as exc:
            raise self._provider_error(GPUErrorCode.TIMEOUT, "GPU agent request timed out.", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise self._provider_error(GPUErrorCode.NETWORK_ERROR, "GPU agent request failed.", retryable=True) from exc
        if response.status_code >= 400:
            raise self._http_error(response, "GPU agent")
        return response.json() if response.content else {}

    async def _resolve_agent_url(self, provider_instance_id: str) -> str:
        status = await self.get_status(provider_instance_id)
        if status.status != GPUInstanceStatus.RUNNING or not status.endpoint_url:
            raise self._provider_error(
                GPUErrorCode.GPU_UNAVAILABLE,
                f"Local GPU agent is not running (status: {status.status.value}).",
                retryable=True,
            )
        return status.endpoint_url

    async def _agent_is_ready(self, endpoint_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0, transport=self._agent_transport) as client:
                response = await client.get(f"{endpoint_url}/health", headers=self._agent_headers())
        except httpx.HTTPError:
            return False
        return response.status_code < 400

    def _agent_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._agent_token:
            headers["Authorization"] = f"Bearer {self._agent_token}"
        return headers

    def _endpoint(self, container_name: str) -> str:
        # Containers on the same Docker network resolve each other by name.
        return f"http://{container_name}:{self._agent_port}"

    @staticmethod
    def _map_status(state: dict) -> GPUInstanceStatus:
        value = str(state.get("Status") or "").lower()
        if value == "running":
            return GPUInstanceStatus.RUNNING
        if value in {"created", "restarting"}:
            return GPUInstanceStatus.STARTING
        if value == "removing":
            return GPUInstanceStatus.STOPPING
        if value == "exited":
            return GPUInstanceStatus.STOPPED if state.get("ExitCode", 0) == 0 else GPUInstanceStatus.FAILED
        if value == "dead":
            return GPUInstanceStatus.FAILED
        return GPUInstanceStatus.UNAVAILABLE

    @staticmethod
    def _parse_log_line(line: str) -> GPULogEntry:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return GPULogEntry(message=line)
        timestamp = payload.get("timestamp")
        parsed_timestamp = None
        if isinstance(timestamp, str):
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                parsed_timestamp = None
        return GPULogEntry(
            stream=str(payload.get("stream") or "stdout"),
            message=str(payload.get("message") or ""),
            timestamp=parsed_timestamp,
        )

    def _http_error(self, response: httpx.Response, source: str) -> GPUProviderException:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {}
        message = f"{source} request failed with HTTP {response.status_code}."
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("detail")
            if detail:
                message = f"{source}: {detail}"
        code = GPUErrorCode.NOT_FOUND if response.status_code == 404 else GPUErrorCode.API_ERROR
        if "could not select device driver" in message.lower():
            code = GPUErrorCode.GPU_UNAVAILABLE
            message = (
                "Docker could not attach the NVIDIA GPU. Enable GPU support in Docker Desktop "
                "(WSL 2 backend) and make sure the NVIDIA driver is installed."
            )
        return self._provider_error(code, message, status_code=response.status_code)

    @staticmethod
    def _provider_error(
        code: GPUErrorCode,
        message: str,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> GPUProviderException:
        return GPUProviderException(
            GPUProviderError(code=code, message=message, retryable=retryable, status_code=status_code)
        )
