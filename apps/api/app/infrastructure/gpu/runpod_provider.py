from collections.abc import AsyncIterator
from datetime import datetime
import asyncio
import json
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.domain.gpu import (
    GPUCommand,
    GPUCommandResult,
    GPUCreateConfig,
    GPUDownloadResult,
    GPUErrorCode,
    GPUHealthResult,
    GPULogEntry,
    GPUProviderError,
    GPUProviderInstance,
    GPUStatusResult,
    GPUUploadFile,
    GPUUploadResult,
    GPUInstanceStatus,
)
from app.infrastructure.gpu.base import GPUProvider, GPUProviderException

logger = logging.getLogger(__name__)

# RunPod's API only accepts full gpuTypeIds (POST /pods returns 400 for "A100"), so
# short names from configuration are expanded to the matching IDs.
_GPU_TYPE_ALIASES: dict[str, list[str]] = {
    "A100": ["NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"],
    "A100-40GB": ["NVIDIA A100-SXM4-40GB"],
    "H100": ["NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"],
    "A40": ["NVIDIA A40"],
    "L40S": ["NVIDIA L40S"],
    "L4": ["NVIDIA L4"],
    "RTX4090": ["NVIDIA GeForce RTX 4090"],
}
_MAX_LOGGED_ERROR_BODY = 8000


class RunPodProvider(GPUProvider):
    def __init__(
        self,
        api_key: str | None = None,
        template_id: str | None = None,
        default_gpu: str | None = None,
        volume_size_gb: int | None = None,
        container_disk_gb: int | None = None,
        region: str | None = None,
        base_url: str = "https://rest.runpod.io/v1",
        agent_port: int | None = None,
        agent_token: str | None = None,
        cloud_type: str | None = None,
        allowed_cuda_versions: list[str] | None = None,
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.runpod_api_key
        self._template_id = template_id or settings.runpod_template_id
        self._default_gpu = default_gpu or settings.runpod_default_gpu
        self._volume_size_gb = volume_size_gb or settings.runpod_volume_size
        self._container_disk_gb = container_disk_gb or settings.runpod_container_disk
        self._region = region if region is not None else settings.runpod_region
        self._base_url = base_url.rstrip("/")
        self._agent_port = agent_port or settings.runpod_agent_port
        self._agent_token = agent_token if agent_token is not None else settings.gpu_agent_token
        self._cloud_type = cloud_type or settings.runpod_cloud_type
        self._allowed_cuda_versions = (
            allowed_cuda_versions
            if allowed_cuda_versions is not None
            else [value.strip() for value in settings.runpod_allowed_cuda_versions.split(",") if value.strip()]
        )
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def create_instance(self, config: GPUCreateConfig) -> GPUProviderInstance:
        self._require_api_key()
        if not self._agent_token:
            # The pod's agent refuses to start without a token, so fail before renting a GPU.
            raise self._provider_error(
                GPUErrorCode.MISSING_API_KEY,
                "GPU_AGENT_TOKEN must be set so the RunPod GPU agent can authenticate requests.",
                retryable=False,
            )
        payload = self._build_create_payload(config)
        response_payload = await self._request("POST", "/pods", json_payload=payload)
        provider_id = str(response_payload.get("id") or response_payload.get("podId") or "")
        if not provider_id:
            raise self._provider_error(
                GPUErrorCode.API_ERROR,
                "RunPod did not return a pod id.",
                retryable=False,
            )
        return GPUProviderInstance(
            provider_instance_id=provider_id,
            status=self._map_status(response_payload.get("desiredStatus") or response_payload.get("status")),
            endpoint_url=self._extract_agent_url(response_payload),
            metadata=self._public_metadata(response_payload),
        )

    async def terminate_instance(self, provider_instance_id: str) -> GPUStatusResult:
        self._require_api_key()
        response_payload = await self._request("DELETE", f"/pods/{provider_instance_id}")
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=GPUInstanceStatus.STOPPING,
            message="Termination requested.",
            metadata=self._public_metadata(response_payload),
        )

    async def get_status(self, provider_instance_id: str) -> GPUStatusResult:
        status = await self._pod_status(provider_instance_id)
        # desiredStatus is RUNNING as soon as the pod is rented, long before the image is
        # pulled and the agent listens, so only report RUNNING once the agent answers.
        if status.status == GPUInstanceStatus.RUNNING and not (
            status.endpoint_url and await self._agent_is_ready(status.endpoint_url)
        ):
            return status.model_copy(update={"status": GPUInstanceStatus.STARTING})
        return status

    async def _pod_status(self, provider_instance_id: str) -> GPUStatusResult:
        self._require_api_key()
        response_payload = await self._request("GET", f"/pods/{provider_instance_id}")
        return GPUStatusResult(
            provider_instance_id=provider_instance_id,
            status=self._map_status(response_payload.get("desiredStatus") or response_payload.get("status")),
            endpoint_url=self._extract_agent_url(response_payload),
            metadata=self._public_metadata(response_payload),
        )

    async def _agent_is_ready(self, endpoint_url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0, transport=self._transport) as client:
                response = await client.get(f"{endpoint_url.rstrip('/')}/health", headers=self._agent_headers())
        except httpx.HTTPError:
            return False
        return response.status_code < 400

    async def upload_files(
        self,
        provider_instance_id: str,
        files: list[GPUUploadFile],
    ) -> GPUUploadResult:
        started_at = time.monotonic()
        uploaded_files: list[str] = []
        bytes_uploaded = 0
        for file in files:
            byte_counter = _CountingAsyncIterator(file.stream)
            await self._agent_request(
                provider_instance_id,
                "PUT",
                "/files",
                params={"path": file.remote_path},
                content=byte_counter,
                headers={
                    "X-Filename": file.filename,
                    "Content-Type": file.content_type or "application/octet-stream",
                },
            )
            bytes_uploaded += byte_counter.bytes_read
            uploaded_files.append(file.remote_path)
        return GPUUploadResult(
            files=uploaded_files,
            bytes_uploaded=bytes_uploaded,
            duration_seconds=time.monotonic() - started_at,
        )

    async def download_files(
        self,
        provider_instance_id: str,
        remote_path: str,
    ) -> GPUDownloadResult:
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

    async def execute_command(
        self,
        provider_instance_id: str,
        command: GPUCommand,
    ) -> GPUCommandResult:
        payload = {
            "command": command.command,
            "timeout_seconds": command.timeout_seconds,
            "working_directory": command.working_directory,
            "env": command.env,
        }
        response_payload = await self._agent_request(
            provider_instance_id,
            "POST",
            "/commands",
            json_payload=payload,
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
        headers = self._agent_headers()
        async with httpx.AsyncClient(timeout=None, transport=self._transport) as client:
            async with client.stream(
                "GET",
                f"{agent_url}/logs",
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    raise self._agent_error(response)
                async for line in response.aiter_lines():
                    if not line:
                        continue
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
            message=str(response_payload.get("message") or "Health check completed."),
            details=response_payload,
        )

    async def list_instances(self) -> list[GPUStatusResult]:
        self._require_api_key()
        response_payload = await self._request("GET", "/pods")
        pods = response_payload if isinstance(response_payload, list) else response_payload.get("pods", [])
        return [
            GPUStatusResult(
                provider_instance_id=str(pod.get("id") or pod.get("podId") or ""),
                status=self._map_status(pod.get("desiredStatus") or pod.get("status")),
                endpoint_url=self._extract_agent_url(pod),
                metadata=self._public_metadata(pod),
            )
            for pod in pods
            if pod.get("id") or pod.get("podId")
        ]

    async def _request(
        self,
        method: str,
        path: str,
        json_payload: dict | None = None,
    ) -> dict | list:
        last_error: GPUProviderException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.request(
                        method,
                        f"{self._base_url}{path}",
                        headers=self._headers(),
                        json=json_payload,
                    )
                if response.status_code >= 400:
                    raise self._http_error(response)
                return response.json() if response.content else {}
            except httpx.TimeoutException as exc:
                last_error = self._provider_error(
                    GPUErrorCode.TIMEOUT,
                    "RunPod request timed out.",
                    retryable=True,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = self._provider_error(
                    GPUErrorCode.NETWORK_ERROR,
                    "RunPod network request failed.",
                    retryable=True,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
            except GPUProviderException as exc:
                last_error = exc
                if not exc.error.retryable or attempt >= self._max_retries:
                    raise
            await asyncio.sleep(2**attempt * 0.5)
        if last_error:
            raise last_error
        raise self._provider_error(GPUErrorCode.API_ERROR, "RunPod request failed.")

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
        request_headers = {**self._agent_headers(), **(headers or {})}
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds or self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{agent_url}{path}",
                    params=params,
                    json=json_payload,
                    content=content,
                    headers=request_headers,
                )
        except httpx.TimeoutException as exc:
            raise self._provider_error(
                GPUErrorCode.TIMEOUT,
                "GPU control agent request timed out.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise self._provider_error(
                GPUErrorCode.NETWORK_ERROR,
                "GPU control agent request failed.",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            raise self._agent_error(response)
        return response.json() if response.content else {}

    async def _resolve_agent_url(self, provider_instance_id: str) -> str:
        status = await self._pod_status(provider_instance_id)
        agent_url = status.endpoint_url
        if not agent_url:
            raise self._provider_error(
                GPUErrorCode.GPU_UNAVAILABLE,
                "GPU control agent endpoint is not available yet.",
                retryable=True,
            )
        return agent_url.rstrip("/")

    def _build_create_payload(self, config: GPUCreateConfig) -> dict:
        template_id = self._template_id
        payload: dict[str, Any] = {
            "name": config.name,
            "computeType": "GPU",
            "cloudType": self._cloud_type,
            "gpuTypeIds": self._resolve_gpu_types(config.gpu_type or self._default_gpu),
            "gpuCount": 1,
            "allowedCudaVersions": self._allowed_cuda_versions,
            "volumeInGb": config.volume_size_gb or self._volume_size_gb,
            "volumeMountPath": "/workspace",
            "containerDiskInGb": config.container_disk_gb or self._container_disk_gb,
            # The template sets no env, so the agent's token and port are passed per pod.
            "env": {**config.env, "GPU_AGENT_TOKEN": self._agent_token, "PORT": str(self._agent_port)},
            "ports": self._format_ports(config.ports),
        }
        image = config.image
        if template_id:
            payload["templateId"] = template_id
        if image:
            payload["imageName"] = image
        if config.region or self._region:
            payload["dataCenterIds"] = [config.region or self._region]
        return {key: value for key, value in payload.items() if value not in (None, [], {})}

    @staticmethod
    def _resolve_gpu_types(value: str) -> list[str]:
        resolved: list[str] = []
        for item in (part.strip() for part in value.split(",")):
            if not item:
                continue
            for gpu_type in _GPU_TYPE_ALIASES.get(item.upper().replace(" ", ""), [item]):
                if gpu_type not in resolved:
                    resolved.append(gpu_type)
        return resolved

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _agent_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._agent_token:
            headers["Authorization"] = f"Bearer {self._agent_token}"
        return headers

    def _require_api_key(self) -> None:
        if not self._api_key:
            raise self._provider_error(
                GPUErrorCode.MISSING_API_KEY,
                "RUNPOD_API_KEY is not configured.",
                retryable=False,
            )

    @staticmethod
    def _public_metadata(payload: dict) -> dict:
        # Pod responses echo env, which holds GPU_AGENT_TOKEN; metadata is stored and shown to users.
        return {key: value for key, value in payload.items() if key != "env"}

    def _http_error(self, response: httpx.Response) -> GPUProviderException:
        body = response.text[:_MAX_LOGGED_ERROR_BODY]
        if self._agent_token:
            body = body.replace(self._agent_token, "[REDACTED]")
        logger.error(
            "RunPod API %s %s returned HTTP %s: %s",
            response.request.method,
            response.request.url.path,
            response.status_code,
            body,
        )
        code = GPUErrorCode.API_ERROR
        retryable = response.status_code >= 500
        if response.status_code in {401, 403}:
            code = GPUErrorCode.AUTHENTICATION_FAILED
        elif response.status_code == 404:
            code = GPUErrorCode.NOT_FOUND
        elif response.status_code == 429:
            code = GPUErrorCode.RATE_LIMIT
            retryable = True
        elif response.status_code in {409, 422}:
            code = GPUErrorCode.GPU_UNAVAILABLE
        message = self._extract_error_message(response)
        if "quota" in message.lower():
            code = GPUErrorCode.QUOTA_EXCEEDED
        return self._provider_error(code, message, retryable, response.status_code)

    def _agent_error(self, response: httpx.Response) -> GPUProviderException:
        return self._provider_error(
            GPUErrorCode.API_ERROR,
            self._extract_error_message(response),
            retryable=response.status_code >= 500,
            status_code=response.status_code,
        )

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            return response.text.strip()[:500] or "GPU provider request failed."
        # RunPod's REST API reports schema violations as a list:
        # [{"error": "...", "problems": ["At /pods/properties/gpuTypeIds/items/enum: ..."]}]
        if isinstance(payload, list):
            messages = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                problems = item.get("problems")
                if isinstance(problems, list) and problems:
                    messages.extend(str(problem)[:300] for problem in problems)
                elif item.get("error"):
                    messages.append(str(item["error"]))
            if messages:
                return "; ".join(messages)[:1000]
        if isinstance(payload, dict):
            error = payload.get("error") or payload.get("message") or payload.get("detail")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if error:
                return str(error)
            errors = payload.get("errors")
            if errors:
                return str(errors)
        return "GPU provider request failed."

    def _format_ports(self, ports: list[int] | list[str] | None) -> list[str]:
        values = ports or [self._agent_port]
        formatted: list[str] = []
        for port in values:
            if isinstance(port, int):
                formatted.append(f"{port}/http")
                continue
            value = str(port)
            formatted.append(value if "/" in value else f"{value}/http")
        return formatted

    def _extract_agent_url(self, payload: dict) -> str | None:
        metadata_url = payload.get("endpointUrl") or payload.get("agentUrl")
        if metadata_url:
            return str(metadata_url)
        public_ip = payload.get("publicIp") or payload.get("ip")
        ports = payload.get("portMappings") or payload.get("ports") or {}
        if not public_ip:
            return self._proxy_url(payload)
        if isinstance(ports, dict):
            mapped_port = ports.get(str(self._agent_port)) or ports.get(self._agent_port)
            if mapped_port:
                return f"http://{public_ip}:{mapped_port}"
        if isinstance(ports, list):
            for item in ports:
                if not isinstance(item, dict):
                    continue
                private_port = item.get("privatePort") or item.get("containerPort")
                public_port = item.get("publicPort") or item.get("hostPort")
                if private_port == self._agent_port and public_port:
                    return f"http://{public_ip}:{public_port}"
        return self._proxy_url(payload)

    def _proxy_url(self, payload: dict) -> str | None:
        # Ports exposed as "<port>/http" are served through RunPod's HTTPS proxy, not portMappings.
        pod_id = payload.get("id") or payload.get("podId")
        ports = payload.get("ports") or []
        if pod_id and isinstance(ports, list) and f"{self._agent_port}/http" in ports:
            return f"https://{pod_id}-{self._agent_port}.proxy.runpod.net"
        return None

    @staticmethod
    def _map_status(status: object) -> GPUInstanceStatus:
        value = str(status or "").lower()
        if value in {"running", "ready"}:
            return GPUInstanceStatus.RUNNING
        if value in {"pending", "queued"}:
            return GPUInstanceStatus.PENDING
        if value in {"starting", "initializing", "creating"}:
            return GPUInstanceStatus.STARTING
        if value in {"stopping", "terminating", "deleting"}:
            return GPUInstanceStatus.STOPPING
        if value in {"stopped", "terminated", "deleted", "exited"}:
            return GPUInstanceStatus.STOPPED
        if value in {"failed", "error"}:
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

    @staticmethod
    def _provider_error(
        code: GPUErrorCode,
        message: str,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> GPUProviderException:
        return GPUProviderException(
            GPUProviderError(
                code=code,
                message=message,
                retryable=retryable,
                status_code=status_code,
            )
        )


class _CountingAsyncIterator:
    def __init__(self, stream: AsyncIterator[bytes]):
        self._stream = stream
        self.bytes_read = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        chunk = await self._stream.__anext__()
        self.bytes_read += len(chunk)
        return chunk
