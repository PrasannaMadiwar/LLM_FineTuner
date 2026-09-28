import asyncio
import json

import httpx
import pytest

from app.domain.gpu import GPUCommand, GPUCreateConfig, GPUErrorCode, GPUInstanceStatus
from app.infrastructure.gpu.base import GPUProviderException
from app.infrastructure.gpu.local_docker_provider import LocalDockerProvider


class FakeDocker:
    def __init__(self, running: list[dict] | None = None, image_exists: bool = True):
        self.requests: list[httpx.Request] = []
        self.running = running or []
        self.image_exists = image_exists
        self.containers: dict[str, dict] = {}

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "GET" and path == "/containers/json":
            return httpx.Response(200, json=self.running)
        if request.method == "POST" and path == "/containers/create":
            if not self.image_exists:
                return httpx.Response(404, json={"message": "No such image: llm-finetuner-gpu-agent:local"})
            name = request.url.params["name"]
            self.containers["abc123"] = {"Name": f"/{name}", "State": {"Status": "running", "ExitCode": 0}}
            return httpx.Response(201, json={"Id": "abc123"})
        if request.method == "POST" and path == "/containers/abc123/start":
            return httpx.Response(204)
        if request.method == "GET" and path.startswith("/containers/") and path.endswith("/json"):
            container = self.containers.get(path.split("/")[2])
            return httpx.Response(200, json=container) if container else httpx.Response(404, json={"message": "gone"})
        if request.method == "POST" and path.endswith("/stop"):
            return httpx.Response(204)
        if request.method == "DELETE":
            self.containers.pop(path.split("/")[2], None)
            return httpx.Response(204)
        return httpx.Response(500, json={"message": f"unexpected {request.method} {path}"})


def _provider(docker: FakeDocker, agent_handler=None, agent_token: str = "secret-token") -> LocalDockerProvider:
    async def healthy_agent(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    return LocalDockerProvider(
        socket_path="/var/run/docker.sock",
        image="llm-finetuner-gpu-agent:local",
        network="llm-finetuner-net",
        workspace_volume="gpu-workspace",
        hf_cache_volume="hf-cache",
        agent_port=8001,
        agent_token=agent_token,
        docker_transport=httpx.MockTransport(docker.handler),
        agent_transport=httpx.MockTransport(agent_handler or healthy_agent),
    )


def test_local_provider_starts_gpu_container_on_the_compose_network():
    docker = FakeDocker()

    instance = _run(_provider(docker).create_instance(GPUCreateConfig(name="training-1")))

    create_request = next(r for r in docker.requests if r.url.path == "/containers/create")
    body = json.loads(create_request.content)
    assert body["Image"] == "llm-finetuner-gpu-agent:local"
    assert "GPU_AGENT_TOKEN=secret-token" in body["Env"]
    assert body["HostConfig"]["DeviceRequests"][0]["Capabilities"] == [["gpu"]]
    assert body["HostConfig"]["NetworkMode"] == "llm-finetuner-net"
    assert {mount["Target"] for mount in body["HostConfig"]["Mounts"]} == {"/workspace", "/opt/hf-cache"}
    assert instance.provider_instance_id == "abc123"
    assert instance.status == GPUInstanceStatus.STARTING
    container_name = create_request.url.params["name"]
    assert instance.endpoint_url == f"http://{container_name}:8001"


def test_local_provider_refuses_second_container_while_gpu_is_busy():
    docker = FakeDocker(running=[{"Id": "busy", "Names": ["/llm-finetuner-gpu-busy"]}])

    with pytest.raises(GPUProviderException) as exc_info:
        _run(_provider(docker).create_instance(GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.GPU_UNAVAILABLE
    assert "llm-finetuner-gpu-busy" in exc_info.value.error.message
    assert not any(r.url.path == "/containers/create" for r in docker.requests)


def test_local_provider_requires_agent_token():
    with pytest.raises(GPUProviderException) as exc_info:
        _run(_provider(FakeDocker(), agent_token="").create_instance(GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.MISSING_API_KEY


def test_local_provider_explains_how_to_build_a_missing_image():
    with pytest.raises(GPUProviderException) as exc_info:
        _run(_provider(FakeDocker(image_exists=False)).create_instance(GPUCreateConfig()))

    assert exc_info.value.error.code == GPUErrorCode.NOT_FOUND
    assert "docker build -t llm-finetuner-gpu-agent:local gpu-agent" in exc_info.value.error.message


def test_local_provider_reports_starting_until_agent_answers():
    docker = FakeDocker()

    async def unreachable_agent(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(docker, agent_handler=unreachable_agent)
    _run(provider.create_instance(GPUCreateConfig()))

    assert _run(provider.get_status("abc123")).status == GPUInstanceStatus.STARTING
    assert _run(_provider(docker).get_status("abc123")).status == GPUInstanceStatus.RUNNING


def test_local_provider_maps_exited_and_removed_containers():
    docker = FakeDocker()
    docker.containers["crashed"] = {"Name": "/c", "State": {"Status": "exited", "ExitCode": 1}}
    provider = _provider(docker)

    assert _run(provider.get_status("crashed")).status == GPUInstanceStatus.FAILED
    assert _run(provider.get_status("missing")).status == GPUInstanceStatus.STOPPED


def test_local_provider_terminate_removes_container():
    docker = FakeDocker()
    provider = _provider(docker)
    _run(provider.create_instance(GPUCreateConfig()))

    result = _run(provider.terminate_instance("abc123"))

    assert result.status == GPUInstanceStatus.STOPPED
    assert "abc123" not in docker.containers


def test_local_provider_sends_agent_token_on_agent_requests():
    docker = FakeDocker()
    seen_headers = []

    async def agent(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get("authorization"))
        if request.url.path == "/commands":
            return httpx.Response(200, json={"stdout": "ok", "stderr": "", "exit_code": 0})
        return httpx.Response(200, json={"status": "ok"})

    provider = _provider(docker, agent_handler=agent)
    _run(provider.create_instance(GPUCreateConfig()))

    result = _run(provider.execute_command("abc123", GPUCommand(command="ls")))

    assert result.stdout == "ok"
    assert seen_headers and all(header == "Bearer secret-token" for header in seen_headers)


def _run(coro):
    return asyncio.run(coro)
