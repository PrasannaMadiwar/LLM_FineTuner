from app.core.config import get_settings
from app.domain.datasets import (
    DatasetMetadata,
    DatasetSearchResult,
    DatasetSource,
    MappingResult,
    NormalizedConversation,
    SemanticMapping,
    ValidationReport,
)
from app.infrastructure.datasets.base import DatasetProvider
from app.infrastructure.repositories.dataset_repository import DatasetRepository
from app.services.dataset_converter_service import DatasetConverterService
from app.services.dataset_validation_service import DatasetValidationService
from app.services.semantic_mapping_service import SemanticMappingService


class DatasetService:
    def __init__(
        self,
        repository: DatasetRepository,
        providers: list[DatasetProvider],
        semantic_mapping_service: SemanticMappingService,
        converter_service: DatasetConverterService,
        validation_service: DatasetValidationService,
    ):
        self._repository = repository
        self._providers = {provider.source: provider for provider in providers}
        self._semantic_mapping_service = semantic_mapping_service
        self._converter_service = converter_service
        self._validation_service = validation_service

    async def search_datasets(
        self,
        query: str,
        source: DatasetSource | None = None,
    ) -> list[DatasetSearchResult]:
        providers = [self._providers[source]] if source else list(self._providers.values())
        results: list[DatasetSearchResult] = []
        for provider in providers:
            results.extend(await provider.search_datasets(query, get_settings().dataset_search_limit))
        return results

    async def get_dataset_info(
        self,
        dataset_id: str,
        source: DatasetSource = DatasetSource.HUGGING_FACE,
        use_cache: bool = True,
    ) -> DatasetMetadata:
        if use_cache:
            cached = await self._repository.get_metadata(dataset_id)
            if cached is not None:
                return cached
        metadata = await self._providers[source].get_dataset_info(dataset_id)
        return await self._repository.save_metadata(metadata)

    async def list_splits(
        self,
        dataset_id: str,
        source: DatasetSource = DatasetSource.HUGGING_FACE,
    ) -> list[str]:
        return await self._providers[source].list_splits(dataset_id)

    async def preview_dataset(
        self,
        dataset_id: str,
        source: DatasetSource = DatasetSource.HUGGING_FACE,
        split: str | None = None,
    ) -> list[dict]:
        return await self._providers[source].preview_dataset(
            dataset_id,
            split,
            get_settings().dataset_preview_rows,
        )

    async def analyze_dataset(
        self,
        dataset_id: str,
        source: DatasetSource = DatasetSource.HUGGING_FACE,
    ) -> MappingResult:
        metadata = await self.get_dataset_info(dataset_id, source)
        return await self._semantic_mapping_service.analyze_dataset(metadata)

    async def normalize_dataset(
        self,
        dataset_id: str,
        source: DatasetSource = DatasetSource.HUGGING_FACE,
        mapping: SemanticMapping | None = None,
        rows: list[dict] | None = None,
        split: str | None = None,
    ) -> tuple[list[NormalizedConversation], ValidationReport]:
        metadata = await self.get_dataset_info(dataset_id, source)
        active_mapping = mapping
        if active_mapping is None:
            active_mapping = await self._semantic_mapping_service.analyze_dataset(metadata)
        active_rows = rows or await self.preview_dataset(dataset_id, source, split)

        validation_report = self._validation_service.validate_rows(active_rows, active_mapping)
        normalized = self._converter_service.convert_rows(active_rows, active_mapping)
        status = "completed" if validation_report.is_valid else "completed_with_issues"
        await self._repository.save_normalization_history(
            dataset_name=metadata.name,
            source=source.value,
            mapping=active_mapping,
            validation_report=validation_report.model_dump(mode="json"),
            normalized_sample=[item.model_dump(mode="json") for item in normalized],
            row_count=len(active_rows),
            status=status,
        )
        return normalized, validation_report
