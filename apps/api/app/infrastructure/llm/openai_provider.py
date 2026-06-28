import asyncio
import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.domain.datasets import DatasetMetadata, LLMErrorCode, LLMProviderError, MappingResult
from app.infrastructure.llm.base import LLMProvider, LLMProviderException


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.openai_model
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def analyze_dataset(self, dataset_metadata: DatasetMetadata) -> MappingResult:
        if not self._api_key:
            raise LLMProviderException(
                LLMProviderError(
                    code=LLMErrorCode.MISSING_API_KEY,
                    message="OPENAI_API_KEY is not configured.",
                    retryable=False,
                )
            )

        payload = self._build_payload(dataset_metadata)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        response_payload = await self._post_with_retries(payload, headers)
        return self._parse_mapping_result(response_payload, dataset_metadata.column_names)

    async def _post_with_retries(self, payload: dict, headers: dict[str, str]) -> dict:
        last_error: LLMProviderException | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        f"{self._base_url}/responses",
                        json=payload,
                        headers=headers,
                    )
                if response.status_code == 429:
                    raise self._provider_error(
                        LLMErrorCode.RATE_LIMIT,
                        "OpenAI rate limit exceeded.",
                        retryable=True,
                        status_code=response.status_code,
                    )
                if response.status_code >= 400:
                    raise self._provider_error(
                        LLMErrorCode.API_ERROR,
                        self._extract_error_message(response),
                        retryable=response.status_code >= 500,
                        status_code=response.status_code,
                    )
                return response.json()
            except httpx.TimeoutException as exc:
                last_error = self._provider_error(
                    LLMErrorCode.TIMEOUT,
                    "OpenAI request timed out.",
                    retryable=True,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = self._provider_error(
                    LLMErrorCode.API_ERROR,
                    "OpenAI request failed.",
                    retryable=True,
                )
                if attempt >= self._max_retries:
                    raise last_error from exc
            except LLMProviderException as exc:
                last_error = exc
                if not exc.error.retryable or attempt >= self._max_retries:
                    raise

            await asyncio.sleep(2**attempt * 0.5)

        if last_error:
            raise last_error
        raise self._provider_error(LLMErrorCode.API_ERROR, "OpenAI request failed.")

    def _build_payload(self, metadata: DatasetMetadata) -> dict:
        prompt_payload = {
            "dataset_name": metadata.name,
            "description": metadata.description,
            "features": metadata.features,
            "columns": metadata.column_names,
            "sample_rows": metadata.sample_rows[:10],
        }
        return {
            "model": self._model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You identify instruction-tuning columns. Return ONLY valid JSON. "
                        "Never return markdown, code, SQL, Python, prose, or shell commands."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this dataset metadata and return JSON with keys: "
                        "user, assistant, system, context, confidence, reasoning.\n"
                        f"{json.dumps(prompt_payload, ensure_ascii=False)}"
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "dataset_semantic_mapping",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "user",
                            "assistant",
                            "system",
                            "context",
                            "confidence",
                            "reasoning",
                        ],
                        "properties": {
                            "user": {"type": "array", "items": {"type": "string"}},
                            "assistant": {"type": "string"},
                            "system": {"type": ["string", "null"]},
                            "context": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string"},
                        },
                    },
                }
            },
        }

    def _parse_mapping_result(self, response_payload: dict, column_names: list[str]) -> MappingResult:
        content = self._extract_output_text(response_payload)
        try:
            payload = json.loads(content)
            mapping = MappingResult(**payload)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise self._provider_error(
                LLMErrorCode.INVALID_RESPONSE,
                "OpenAI returned invalid semantic mapping JSON.",
                retryable=False,
            ) from exc

        missing_columns = self._missing_columns(mapping, column_names)
        if missing_columns:
            raise self._provider_error(
                LLMErrorCode.INVALID_RESPONSE,
                f"OpenAI mapping referenced unknown columns: {', '.join(missing_columns)}",
                retryable=False,
            )
        return mapping

    def _extract_output_text(self, response_payload: dict) -> str:
        if isinstance(response_payload.get("output_text"), str):
            return response_payload["output_text"]

        output = response_payload.get("output", [])
        for item in output:
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    return content["text"]
        raise self._provider_error(
            LLMErrorCode.INVALID_RESPONSE,
            "OpenAI response did not contain output text.",
            retryable=False,
        )

    @staticmethod
    def _missing_columns(mapping: MappingResult, column_names: list[str]) -> list[str]:
        available_columns = set(column_names)
        mapped_columns = [*mapping.user, mapping.assistant, *mapping.context]
        if mapping.system:
            mapped_columns.append(mapping.system)
        return [column for column in mapped_columns if column not in available_columns]

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload: Any = response.json()
        except json.JSONDecodeError:
            return "OpenAI API error."
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
        return "OpenAI API error."

    @staticmethod
    def _provider_error(
        code: LLMErrorCode,
        message: str,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> LLMProviderException:
        return LLMProviderException(
            LLMProviderError(
                code=code,
                message=message,
                retryable=retryable,
                status_code=status_code,
            )
        )
