import asyncio
import json

import httpx
import pytest

from app.domain.gpu import GPUCommand, GPUCreateConfig, GPUErrorCode, GPUInstanceStatus
from app.infrastructure.gpu.base import GPUProviderException
from app.infrastructure.gpu.runpod_provider import RunPodProvider


def test_runpod_provider_creates_pod_and_maps_status():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "pod-1",
                "status": "RUNNING",
                "publicIp": "127.0.0.1",
                "portMappings": {"8001": 18001},
            },
        )

    provider = RunPodProvider(
        api_key="runpod-key",
        template_id="template-1",
        default_gpu="A100",
        base_url="https://runpod.test/v1",
        transport=httpx.MockTransport(handler),
    )

    instance = _run(provider.create_instance(GPUCreateConfig(name="test-gpu")))

    assert instance.provider_instance_id == "pod-1"
    assert instance.status == GPUInstanceStatus.RUNNING
    assert instance.endpoint_url == "http://127.0.0.1:18001"
    assert requests[0].url == "https://runpod.test/v1/pods"
    payload = json.loads(requests[0].content)
    assert payload["templateId"] == "template-1"
    assert payload["ports"] == ["8001/http"]
    assert requests[0].headers["authorization"] == "Bearer runpod-key"


def test_runpod_provider_returns_structured_rate_limit_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Too many requests"}})

    provider = RunPodProvider(
        api_key="runpod-key",
        base_url="https://runpod.test/v1",
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(GPUProviderException) as exc_info:
        _run(provider.list_instances())

    assert exc_info.value.error.code == GPUErrorCode.RATE_LIMIT
    assert exc_info.value.error.retryable is True


def test_runpod_provider_executes_command_through_agent_endpoint():
    seen_command_payloads = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url == "https://runpod.test/v1/pods/pod-1":
            return httpx.Response(
                200,
                json={
                    "id": "pod-1",
                    "status": "RUNNING",
                    "publicIp": "127.0.0.1",
                    "portMappings": {"8001": 18001},
                },
            )
        if request.url == "http://127.0.0.1:18001/commands":
            seen_command_payloads.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "stdout": "done",
                    "stderr": "",
                    "exit_code": 0,
                    "execution_time_seconds": 1.5,
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    provider = RunPodProvider(
        api_key="runpod-key",
        base_url="https://runpod.test/v1",
        transport=httpx.MockTransport(handler),
    )

    result = _run(provider.execute_command("pod-1", GPUCommand(command="python train.py")))

    assert result.stdout == "done"
    assert result.exit_code == 0
    assert seen_command_payloads[0]["command"] == "python train.py"


def _run(coro):
    return asyncio.run(coro)
