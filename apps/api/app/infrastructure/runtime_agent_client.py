import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings


class RuntimeAgentError(Exception):
    pass


class RuntimeTrainingStart(BaseModel):
    training_id: str
    state: str


class RuntimeTrainingStatus(BaseModel):
    training_id: str
    state: str
    current_epoch: float | None = None
    loss: float | None = None
    learning_rate: float | None = None
    eta_seconds: float | None = None
    global_step: int | None = None
    metrics: dict = Field(default_factory=dict)
    checkpoints: list[str] = Field(default_factory=list)
    error: str | None = None


class RuntimeArtifact(BaseModel):
    path: str
    size_bytes: int


class RuntimeArtifactList(BaseModel):
    training_id: str
    artifacts: list[RuntimeArtifact] = Field(default_factory=list)


class RuntimeAgentClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._token = get_settings().gpu_agent_token

    async def health(self) -> dict:
        return await self._request("GET", "/health")

    async def upload_json(self, remote_path: str, payload: dict) -> None:
        content = json.dumps(payload, indent=2).encode("utf-8")
        await self._request(
            "PUT",
            "/files",
            params={"path": remote_path},
            content=_single_chunk(content),
            headers={"Content-Type": "application/json"},
        )

    async def upload_file(self, local_path: Path, remote_path: str) -> None:
        await self._request(
            "PUT",
            "/files",
            params={"path": remote_path},
            content=_file_chunks(local_path),
            headers={"Content-Type": "application/octet-stream"},
        )

    async def start_training(
        self,
        template: str,
        dataset_path: str,
        config: dict,
        model: str | None = None,
    ) -> RuntimeTrainingStart:
        payload = {"template": template, "model": model, "dataset_path": dataset_path, "config": config}
        response = await self._request("POST", "/train", json_payload=payload)
        return RuntimeTrainingStart(**response)

    async def status(self, training_id: str) -> RuntimeTrainingStatus:
        response = await self._request("GET", f"/status/{training_id}")
        return RuntimeTrainingStatus(**response)

    async def cancel(self, training_id: str) -> RuntimeTrainingStatus:
        response = await self._request("POST", f"/cancel/{training_id}")
        return RuntimeTrainingStatus(**response)

    async def artifacts(self, training_id: str) -> RuntimeArtifactList:
        response = await self._request("GET", f"/artifacts/{training_id}")
        return RuntimeArtifactList(**response)

    async def cleanup(self) -> dict:
        return await self._request("POST", "/cleanup")

    async def wait_for_completion(
        self,
        training_id: str,
        poll_interval_seconds: float,
        timeout_seconds: int,
    ) -> RuntimeTrainingStatus:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() <= deadline:
            status = await self.status(training_id)
            if status.state in {"succeeded", "failed", "cancelled"}:
                return status
            await asyncio.sleep(poll_interval_seconds)
        raise RuntimeAgentError("Timed out waiting for GPU agent training to finish.")

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_payload: dict | None = None,
        content: AsyncIterator[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    params=params,
                    json=json_payload,
                    content=content,
                    headers=self._headers(headers),
                )
        except httpx.HTTPError as exc:
            raise RuntimeAgentError("GPU agent request failed.") from exc
        if response.status_code >= 400:
            raise RuntimeAgentError(_extract_error_message(response))
        return response.json() if response.content else {}

    def _headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        merged = dict(headers or {})
        if self._token:
            merged["Authorization"] = f"Bearer {self._token}"
        return merged or None


async def _single_chunk(content: bytes) -> AsyncIterator[bytes]:
    yield content


async def _file_chunks(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            yield chunk


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return "GPU agent request failed."
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if detail:
            return str(detail)
    return "GPU agent request failed."
