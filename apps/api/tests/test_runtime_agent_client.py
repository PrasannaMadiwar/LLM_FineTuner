import asyncio
import json

import httpx

from app.infrastructure.runtime_agent_client import RuntimeAgentClient


def test_runtime_agent_client_starts_and_polls_training():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/train":
            return httpx.Response(200, json={"training_id": "run-1", "state": "queued"})
        if request.url.path == "/status/run-1":
            return httpx.Response(
                200,
                json={"training_id": "run-1", "state": "succeeded", "loss": 0.1},
            )
        if request.url.path == "/artifacts/run-1":
            return httpx.Response(
                200,
                json={
                    "training_id": "run-1",
                    "artifacts": [{"path": "artifacts/run-1/model.txt", "size_bytes": 4}],
                },
            )
        return httpx.Response(404, json={"detail": "missing"})

    client = RuntimeAgentClient("http://agent.test", transport=httpx.MockTransport(handler))

    started = asyncio.run(client.start_training("llama", "dataset/train.jsonl", {"epochs": 1}))
    status = asyncio.run(client.wait_for_completion("run-1", 0, 1))
    artifacts = asyncio.run(client.artifacts("run-1"))

    assert started.training_id == "run-1"
    assert status.state == "succeeded"
    assert artifacts.artifacts[0].path == "artifacts/run-1/model.txt"
    assert json.loads(requests[0].content)["dataset_path"] == "dataset/train.jsonl"
