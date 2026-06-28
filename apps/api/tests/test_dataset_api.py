from fastapi.testclient import TestClient

from app.api.dependencies import get_dataset_service
from app.domain.datasets import (
    DatasetMetadata,
    DatasetSearchResult,
    DatasetSource,
    MappingResult,
)
from app.main import app


class FakeDatasetService:
    async def search_datasets(self, query, source=None):
        return [DatasetSearchResult(dataset_id="demo", name="demo", source=DatasetSource.HUGGING_FACE)]

    async def get_dataset_info(self, dataset_id, source=DatasetSource.HUGGING_FACE):
        return DatasetMetadata(
            dataset_id=dataset_id,
            name=dataset_id,
            source=source,
            column_names=["instruction", "output"],
            sample_rows=[{"instruction": "Say hi", "output": "Hi"}],
        )

    async def preview_dataset(self, dataset_id, source=DatasetSource.HUGGING_FACE, split=None):
        return [{"instruction": "Say hi", "output": "Hi"}]

    async def analyze_dataset(self, dataset_id, source=DatasetSource.HUGGING_FACE):
        return MappingResult(
            user=["instruction"],
            assistant="output",
            confidence=1.0,
            reasoning="Instruction and output columns match instruction-tuning roles.",
        )

    async def normalize_dataset(
        self,
        dataset_id,
        source=DatasetSource.HUGGING_FACE,
        mapping=None,
        rows=None,
        split=None,
    ):
        from app.domain.datasets import NormalizedConversation, NormalizedMessage, ValidationReport

        return (
            [
                NormalizedConversation(
                    messages=[
                        NormalizedMessage(role="user", content="Say hi"),
                        NormalizedMessage(role="assistant", content="Hi"),
                    ]
                )
            ],
            ValidationReport(is_valid=True, total_rows=1, valid_rows=1),
        )


def test_dataset_search_api():
    client = _client()

    response = client.get("/api/v1/datasets/search", params={"query": "alpaca"})

    assert response.status_code == 200
    assert response.json()["results"][0]["dataset_id"] == "demo"


def test_dataset_info_api_supports_slash_dataset_ids():
    client = _client()

    response = client.get("/api/v1/datasets/info/tatsu-lab/alpaca")

    assert response.status_code == 200
    assert response.json()["metadata"]["dataset_id"] == "tatsu-lab/alpaca"


def test_dataset_analyze_api():
    client = _client()

    response = client.post("/api/v1/datasets/analyze", json={"dataset_id": "demo"})

    assert response.status_code == 200
    assert response.json()["mapping"]["assistant"] == "output"


def test_dataset_normalize_api():
    client = _client()

    response = client.post(
        "/api/v1/datasets/normalize",
        json={
            "dataset_id": "demo",
            "mapping": {"user": ["instruction"], "assistant": "output", "system": None, "context": []},
            "rows": [{"instruction": "Say hi", "output": "Hi"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["validation_report"]["is_valid"] is True


def _client():
    app.dependency_overrides[get_dataset_service] = lambda: FakeDatasetService()
    return TestClient(app)
