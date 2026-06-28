import asyncio

from app.domain.datasets import DatasetMetadata, DatasetSearchResult, DatasetSource, MappingResult
from app.services.dataset_converter_service import DatasetConverterService
from app.services.dataset_service import DatasetService
from app.services.dataset_validation_service import DatasetValidationService


class FakeRepository:
    def __init__(self):
        self.metadata = None
        self.history_saved = False

    async def get_metadata(self, dataset_id):
        return self.metadata

    async def save_metadata(self, metadata):
        self.metadata = metadata
        return metadata

    async def save_normalization_history(self, **kwargs):
        self.history_saved = True


class FakeProvider:
    source = DatasetSource.HUGGING_FACE

    async def search_datasets(self, query, limit):
        return [
            DatasetSearchResult(dataset_id="demo", name="demo", source=self.source, description=query)
        ]

    async def get_dataset_info(self, dataset_id):
        return DatasetMetadata(
            dataset_id=dataset_id,
            name=dataset_id,
            source=self.source,
            column_names=["instruction", "output"],
            sample_rows=[{"instruction": "Say hi", "output": "Hi"}],
        )

    async def list_splits(self, dataset_id):
        return ["train"]

    async def preview_dataset(self, dataset_id, split, limit):
        return [{"instruction": "Say hi", "output": "Hi"}]


class FakeSemanticMappingService:
    async def analyze_dataset(self, metadata):
        return MappingResult(
            user=["instruction"],
            assistant="output",
            confidence=0.95,
            reasoning="Instruction and output columns match instruction-tuning roles.",
        )


def test_dataset_service_searches_provider():
    service = _service()

    results = asyncio.run(service.search_datasets("instruction"))

    assert results[0].dataset_id == "demo"


def test_dataset_service_normalizes_preview_rows_and_records_history():
    repository = FakeRepository()
    service = _service(repository)

    normalized, report = asyncio.run(service.normalize_dataset("demo"))

    assert report.is_valid is True
    assert normalized[0].messages[0].role == "user"
    assert repository.history_saved is True


def _service(repository=None):
    return DatasetService(
        repository=repository or FakeRepository(),
        providers=[FakeProvider()],
        semantic_mapping_service=FakeSemanticMappingService(),
        converter_service=DatasetConverterService(),
        validation_service=DatasetValidationService(),
    )
