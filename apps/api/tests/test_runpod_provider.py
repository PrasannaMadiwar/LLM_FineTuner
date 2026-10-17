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
        agent_token="agent-token",
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


def _provider(handler, **kwargs) -> RunPodProvider:
    options = {
        "api_key": "runpod-key",
        "template_id": "template-1",
        "default_gpu": "A100",
        "agent_token": "agent-token",
        "base_url": "https://runpod.test/v1",
        "max_retries": 0,
        "transport": httpx.MockTransport(handler),
        **kwargs,
    }
    return RunPodProvider(**options)


def _capture_create_payload(**kwargs) -> dict:
    sent = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "pod-1", "desiredStatus": "RUNNING", "ports": ["8001/http"]})

    _run(_provider(handler, **kwargs).create_instance(GPUCreateConfig(name="job")))
    return sent[0]


def test_create_payload_matches_runpod_pod_create_schema():
    payload = _capture_create_payload()

    assert payload == {
        "name": "job",
        "computeType": "GPU",
        "cloudType": "SECURE",
        "gpuTypeIds": ["NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"],
        "gpuCount": 1,
        "allowedCudaVersions": ["12.8", "12.9", "13.0"],
        "volumeInGb": 100,
        "volumeMountPath": "/workspace",
        "containerDiskInGb": 50,
        "env": {"GPU_AGENT_TOKEN": "agent-token", "PORT": "8001"},
        "ports": ["8001/http"],
        "templateId": "template-1",
    }


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("A100", ["NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"]),
        ("h100", ["NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"]),
        ("RTX 4090", ["NVIDIA GeForce RTX 4090"]),
        ("NVIDIA L40S", ["NVIDIA L40S"]),
        ("NVIDIA L40S, A40,NVIDIA L40S", ["NVIDIA L40S", "NVIDIA A40"]),
    ],
)
def test_gpu_aliases_expand_to_runpod_gpu_type_ids(configured, expected):
    assert _capture_create_payload(default_gpu=configured)["gpuTypeIds"] == expected


def test_create_refuses_without_agent_token_and_sends_nothing():
    sent = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"id": "pod-1"})

    with pytest.raises(GPUProviderException) as exc_info:
        _run(_provider(handler, agent_token="").create_instance(GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.MISSING_API_KEY
    assert sent == []


def test_runpod_schema_error_list_is_surfaced_and_logged(caplog):
    body = [
        {
            "error": "The request body does not meet the schema requirements.",
            "problems": ["At /pods/properties/gpuTypeIds/items/enum: value must be one of 'NVIDIA A40'"],
        }
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=body)

    with caplog.at_level("ERROR"), pytest.raises(GPUProviderException) as exc_info:
        _run(_provider(handler).create_instance(GPUCreateConfig()))

    assert exc_info.value.error.status_code == 400
    assert "gpuTypeIds/items/enum" in exc_info.value.error.message
    assert "gpuTypeIds/items/enum" in caplog.text
    assert "HTTP 400" in caplog.text


def test_logged_error_body_redacts_agent_token(caplog):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "bad env", "env": {"GPU_AGENT_TOKEN": "agent-token"}})

    with caplog.at_level("ERROR"), pytest.raises(GPUProviderException):
        _run(_provider(handler).create_instance(GPUCreateConfig()))

    assert "agent-token" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_pod_metadata_never_exposes_env():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "pod-1", "desiredStatus": "RUNNING", "env": {"GPU_AGENT_TOKEN": "agent-token"}},
        )

    instance = _run(_provider(handler).create_instance(GPUCreateConfig()))

    assert "env" not in instance.metadata
    assert "agent-token" not in json.dumps(instance.metadata)


def test_http_port_resolves_to_runpod_proxy_and_waits_for_agent():
    agent_up = {"value": False}
    seen_auth = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "runpod.test":
            return httpx.Response(200, json={"id": "pod-1", "desiredStatus": "RUNNING", "ports": ["8001/http"]})
        assert str(request.url) == "https://pod-1-8001.proxy.runpod.net/health"
        seen_auth.append(request.headers.get("authorization"))
        return httpx.Response(200 if agent_up["value"] else 502, json={"status": "ok"})

    provider = _provider(handler)

    starting = _run(provider.get_status("pod-1"))
    agent_up["value"] = True
    running = _run(provider.get_status("pod-1"))

    assert starting.status == GPUInstanceStatus.STARTING
    assert running.status == GPUInstanceStatus.RUNNING
    assert running.endpoint_url == "https://pod-1-8001.proxy.runpod.net"
    assert seen_auth == ["Bearer agent-token", "Bearer agent-token"]
