import json
from contextlib import aclosing
from pathlib import Path
from uuid import UUID

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
        user_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> tuple[list[NormalizedConversation], ValidationReport, str | None]:
        metadata = await self.get_dataset_info(dataset_id, source)
        active_mapping = mapping
        if active_mapping is None:
            active_mapping = await self._semantic_mapping_service.analyze_dataset(metadata)
        if rows is not None:
            active_rows = rows
            validation_report = self._validation_service.validate_rows(active_rows, active_mapping)
            normalized = self._converter_service.convert_rows(active_rows, active_mapping)
            artifact_path = None
        else:
            normalized, validation_report, artifact_path = await self._normalize_full_dataset(
                dataset_id=dataset_id,
                source=source,
                split=split,
                mapping=active_mapping,
                user_id=user_id,
                project_id=project_id,
            )
            active_rows = [item.model_dump(mode="json") for item in normalized[:10]]

        status = "completed" if validation_report.is_valid else "completed_with_issues"
        await self._repository.save_normalization_history(
            dataset_name=metadata.name,
            source=source.value,
            mapping=active_mapping,
            validation_report=validation_report.model_dump(mode="json"),
            normalized_sample=[item.model_dump(mode="json") for item in normalized],
            row_count=validation_report.total_rows,
            status=status,
            artifact_path=artifact_path,
            user_id=str(user_id) if user_id else None,
            project_id=str(project_id) if project_id else None,
        )
        return normalized, validation_report, artifact_path

    async def _normalize_full_dataset(
        self,
        dataset_id: str,
        source: DatasetSource,
        split: str | None,
        mapping: SemanticMapping,
        user_id: UUID | None,
        project_id: UUID | None,
    ) -> tuple[list[NormalizedConversation], ValidationReport, str]:
        settings = get_settings()
        provider = self._providers[source]
        max_rows = settings.dataset_max_rows
        all_rows: list[dict] = []
        output_path = self._artifact_path(settings.storage_path, dataset_id, source, split, user_id, project_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_sample: list[NormalizedConversation] = []
        invalid_batch_report: ValidationReport | None = None
        # A failed download must fail the request: a partially written file would
        # otherwise be used as training data without anyone noticing.
        try:
            with output_path.open("w", encoding="utf-8", newline="\n") as file:
                row_batches = provider.iter_dataset_rows(dataset_id, split, min(1000, max_rows or 1000))
                async with aclosing(row_batches):
                    async for batch in row_batches:
                        if max_rows is not None:
                            batch = batch[: max_rows - len(all_rows)]
                        report = self._validation_service.validate_rows(batch, mapping)
                        if not report.is_valid:
                            invalid_batch_report = report
                            break
                        converted = self._converter_service.convert_rows(batch, mapping)
                        for item in converted:
                            file.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")
                        all_rows.extend(batch)
                        if len(normalized_sample) < 10:
                            normalized_sample.extend(converted[: 10 - len(normalized_sample)])
                        if max_rows is not None and len(all_rows) >= max_rows:
                            break
        except Exception:
            output_path.unlink(missing_ok=True)
            raise

        if invalid_batch_report is not None:
            output_path.unlink(missing_ok=True)
            return [], invalid_batch_report, None

        validation_report = self._validation_service.validate_rows(all_rows, mapping)
        if validation_report.total_rows == 0 or not validation_report.is_valid:
            output_path.unlink(missing_ok=True)
            return normalized_sample, validation_report, None
        return normalized_sample, validation_report, str(output_path)

    @staticmethod
    def _artifact_path(
        storage_path: str,
        dataset_id: str,
        source: DatasetSource,
        split: str | None,
        user_id: UUID | None,
        project_id: UUID | None,
    ) -> Path:
        owner = str(user_id) if user_id else "anonymous"
        project = str(project_id) if project_id else "default"
        safe_dataset = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in dataset_id)
        safe_split = split or "train"
        return Path(storage_path).resolve() / "datasets" / owner / project / source.value / safe_dataset / f"{safe_split}.jsonl"
