import asyncio
import json

import pytest

from app.core.config import get_settings
from app.domain.datasets import DatasetSource, SemanticMapping
from app.infrastructure.datasets.base import DatasetNotFoundError
from app.infrastructure.datasets.demo_provider import DEMO_DATASET_ID, DemoDatasetProvider
from app.services.dataset_converter_service import DatasetConverterService
from app.services.dataset_service import DatasetService
from app.services.dataset_validation_service import DatasetValidationService


class FakeRepository:
    async def get_metadata(self, dataset_id):
        return None

    async def save_metadata(self, metadata):
        return metadata

    async def save_normalization_history(self, **kwargs):
        pass


def test_demo_provider_serves_bundled_rows():
    provider = DemoDatasetProvider()

    info = asyncio.run(provider.get_dataset_info(DEMO_DATASET_ID))
    preview = asyncio.run(provider.preview_dataset(DEMO_DATASET_ID, "train", 3))

    assert info.source == DatasetSource.DEMO
    assert info.column_names == ["instruction", "output"]
    assert info.row_counts["train"] > 400
    assert len(preview) == 3
    assert {"instruction", "output"} <= preview[0].keys()


def test_demo_provider_is_found_by_search_keywords_only():
    provider = DemoDatasetProvider()

    assert asyncio.run(provider.search_datasets("demo", 5))[0].dataset_id == DEMO_DATASET_ID
    assert asyncio.run(provider.search_datasets("alpaca", 5)) == []


def test_demo_provider_rejects_unknown_ids():
    with pytest.raises(DatasetNotFoundError):
        asyncio.run(DemoDatasetProvider().preview_dataset("builtin/other", "train", 3))


def test_demo_dataset_normalizes_into_a_training_file(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    monkeypatch.delenv("DATASET_MAX_ROWS", raising=False)
    get_settings.cache_clear()
    service = DatasetService(
        repository=FakeRepository(),
        providers=[DemoDatasetProvider()],
        semantic_mapping_service=None,
        converter_service=DatasetConverterService(),
        validation_service=DatasetValidationService(),
    )

    _, report, artifact_path = asyncio.run(
        service.normalize_dataset(
            DEMO_DATASET_ID,
            source=DatasetSource.DEMO,
            mapping=SemanticMapping(user=["instruction"], assistant="output"),
            split="train",
        )
    )

    assert report.is_valid is True
    with open(artifact_path, encoding="utf-8") as artifact:
        rows = [json.loads(line) for line in artifact]
    assert len(rows) == report.total_rows
    assert [message["role"] for message in rows[0]["messages"]] == ["user", "assistant"]
    get_settings.cache_clear()
