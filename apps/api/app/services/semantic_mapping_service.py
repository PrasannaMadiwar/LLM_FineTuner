from app.domain.datasets import DatasetMetadata, MappingResult
from app.infrastructure.cache.mapping_cache import MappingCache
from app.infrastructure.llm.base import LLMProvider
from app.infrastructure.repositories.dataset_repository import DatasetRepository


class SemanticMappingService:
    def __init__(
        self,
        repository: DatasetRepository,
        provider: LLMProvider,
        cache: MappingCache | None = None,
    ):
        self._repository = repository
        self._provider = provider
        self._cache = cache

    async def analyze_dataset(self, dataset_metadata: DatasetMetadata) -> MappingResult:
        if self._cache is not None:
            cached_mapping = await self._cache.get(dataset_metadata.name)
            if cached_mapping is not None:
                return cached_mapping

        cached_record = await self._repository.get_mapping(dataset_metadata.name)
        if cached_record is not None:
            if self._cache is not None:
                await self._cache.set(dataset_metadata.name, cached_record.mapping_json)
            return cached_record.mapping_json

        mapping = await self._provider.analyze_dataset(dataset_metadata)
        mapping = self.validate_mapping(mapping, dataset_metadata.column_names)
        await self._repository.save_mapping(dataset_metadata.name, mapping)
        if self._cache is not None:
            await self._cache.set(dataset_metadata.name, mapping)
        return mapping

    def validate_mapping(self, mapping: MappingResult, column_names: list[str]) -> MappingResult:
        available_columns = set(column_names)
        mapped_columns = [*mapping.user, mapping.assistant]
        if mapping.system:
            mapped_columns.append(mapping.system)
        mapped_columns.extend(mapping.context)

        missing_columns = [column for column in mapped_columns if column not in available_columns]
        if missing_columns:
            raise ValueError(f"Mapping references unknown columns: {', '.join(missing_columns)}")
        return mapping
