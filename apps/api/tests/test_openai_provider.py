import json

import httpx
import pytest

from app.domain.datasets import DatasetMetadata, DatasetSource, LLMErrorCode
from app.infrastructure.llm.base import LLMProviderException
from app.infrastructure.llm.openai_provider import OpenAIProvider


def test_openai_provider_posts_responses_payload_and_parses_mapping():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "user": ["instruction", "input"],
                        "assistant": "output",
                        "system": None,
                        "context": [],
                        "confidence": 0.94,
                        "reasoning": "Columns match instruction, optional input, and answer roles.",
                    }
                )
            },
        )

    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-test",
        base_url="https://example.test/v1",
        transport=httpx.MockTransport(handler),
    )

    result = _run(provider.analyze_dataset(_metadata()))

    assert result.user == ["instruction", "input"]
    assert result.assistant == "output"
    assert requests[0].url == "https://example.test/v1/responses"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "gpt-test"
    assert payload["text"]["format"]["name"] == "dataset_semantic_mapping"


def test_openai_provider_rejects_unknown_mapping_columns():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "user": ["missing"],
                        "assistant": "output",
                        "system": None,
                        "context": [],
                        "confidence": 0.5,
                        "reasoning": "Invalid test response.",
                    }
                )
            },
        )

    provider = OpenAIProvider(api_key="test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(LLMProviderException) as exc_info:
        _run(provider.analyze_dataset(_metadata()))

    assert exc_info.value.error.code == LLMErrorCode.INVALID_RESPONSE


def _metadata() -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id="demo",
        name="demo",
        source=DatasetSource.HUGGING_FACE,
        column_names=["instruction", "input", "output"],
        sample_rows=[{"instruction": "Say hi", "input": "", "output": "Hi"}],
    )


def _run(coro):
    import asyncio

    return asyncio.run(coro)
