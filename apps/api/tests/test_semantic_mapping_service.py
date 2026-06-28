import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.datasets import DatasetMetadata, DatasetSource, MappingRecord, MappingResult
from app.services.semantic_mapping_service import SemanticMappingService


class FakeRepository:
    def __init__(self, cached_mapping=None):
        self.cached_mapping = cached_mapping
        self.saved_mapping = None

    async def get_mapping(self, dataset_name):
        return self.cached_mapping

    async def save_mapping(self, dataset_name, mapping):
        self.saved_mapping = mapping
        return MappingRecord(
            id=uuid4(),
            dataset_name=dataset_name,
            mapping_json=mapping,
            confidence=mapping.confidence,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


class FakeMappingClient:
    def __init__(self):
        self.called = False

    async def analyze_dataset(self, dataset_metadata):
        self.called = True
        return MappingResult(
            user=["instruction"],
            assistant="output",
            system=None,
            context=[],
            confidence=0.95,
            reasoning="Instruction and output columns match instruction-tuning roles.",
        )


def test_semantic_mapping_uses_cache_before_llm():
    cached = MappingRecord(
        id=uuid4(),
        dataset_name="demo",
        mapping_json=MappingResult(
            user=["prompt"],
            assistant="answer",
            confidence=1.0,
            reasoning="Cached mapping.",
        ),
        confidence=1.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository = FakeRepository(cached_mapping=cached)
    client = FakeMappingClient()
    service = SemanticMappingService(repository, client)

    result = asyncio.run(service.analyze_dataset(_metadata()))

    assert result == cached.mapping_json
    assert client.called is False


def test_semantic_mapping_validates_and_saves_llm_json():
    repository = FakeRepository()
    client = FakeMappingClient()
    service = SemanticMappingService(repository, client)

    result = asyncio.run(service.analyze_dataset(_metadata()))

    assert result.user == ["instruction"]
    assert repository.saved_mapping.assistant == "output"
    assert client.called is True


def test_semantic_mapping_rejects_unknown_columns():
    service = SemanticMappingService(FakeRepository(), FakeMappingClient())
    mapping = MappingResult(
        user=["missing"],
        assistant="output",
        confidence=0.5,
        reasoning="Invalid mapping for test.",
    )

    try:
        service.validate_mapping(mapping, ["instruction", "output"])
    except ValueError as exc:
        assert "unknown columns" in str(exc)
        return
    raise AssertionError("Unknown columns should raise ValueError.")


def _metadata():
    return DatasetMetadata(
        dataset_id="demo",
        name="demo",
        source=DatasetSource.HUGGING_FACE,
        column_names=["instruction", "output"],
        sample_rows=[{"instruction": "Say hi", "output": "Hi"}],
    )
