from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.datasets import DatasetMetadata, MappingRecord, MappingResult, SemanticMapping
from app.infrastructure.models.dataset import (
    DatasetMappingModel,
    DatasetMetadataCacheModel,
    DatasetNormalizationHistoryModel,
)


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_metadata(self, dataset_id: str) -> DatasetMetadata | None:
        result = await self._session.execute(
            select(DatasetMetadataCacheModel).where(DatasetMetadataCacheModel.dataset_id == dataset_id)
        )
        model = result.scalar_one_or_none()
        return DatasetMetadata(**model.metadata_json) if model else None

    async def save_metadata(self, metadata: DatasetMetadata) -> DatasetMetadata:
        result = await self._session.execute(
            select(DatasetMetadataCacheModel).where(
                DatasetMetadataCacheModel.dataset_id == metadata.dataset_id
            )
        )
        model = result.scalar_one_or_none()
        payload = metadata.model_dump(mode="json")
        if model is None:
            model = DatasetMetadataCacheModel(
                dataset_id=metadata.dataset_id,
                source=metadata.source.value,
                name=metadata.name,
                metadata_json=payload,
            )
            self._session.add(model)
        else:
            model.source = metadata.source.value
            model.name = metadata.name
            model.metadata_json = payload
            model.updated_at = datetime.now(UTC)
        await self._session.commit()
        return metadata

    async def get_mapping(self, dataset_name: str) -> MappingRecord | None:
        result = await self._session.execute(
            select(DatasetMappingModel).where(DatasetMappingModel.dataset_name == dataset_name)
        )
        model = result.scalar_one_or_none()
        return self._to_mapping_record(model) if model else None

    async def save_mapping(
        self,
        dataset_name: str,
        mapping: MappingResult,
    ) -> MappingRecord:
        result = await self._session.execute(
            select(DatasetMappingModel).where(DatasetMappingModel.dataset_name == dataset_name)
        )
        model = result.scalar_one_or_none()
        payload = mapping.model_dump(mode="json")
        if model is None:
            model = DatasetMappingModel(
                dataset_name=dataset_name,
                mapping_json=payload,
                confidence=mapping.confidence,
            )
            self._session.add(model)
        else:
            model.mapping_json = payload
            model.confidence = mapping.confidence
            model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_mapping_record(model)

    async def save_normalization_history(
        self,
        dataset_name: str,
        source: str,
        mapping: SemanticMapping,
        validation_report: dict,
        normalized_sample: list[dict],
        row_count: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        model = DatasetNormalizationHistoryModel(
            dataset_name=dataset_name,
            source=source,
            mapping_json=mapping.model_dump(mode="json"),
            validation_report_json=validation_report,
            normalized_sample_json=normalized_sample,
            row_count=row_count,
            status=status,
            error_message=error_message,
        )
        self._session.add(model)
        await self._session.commit()

    @staticmethod
    def _to_mapping_record(model: DatasetMappingModel) -> MappingRecord:
        mapping_payload = dict(model.mapping_json)
        mapping_payload.setdefault("confidence", model.confidence)
        mapping_payload.setdefault("reasoning", "Cached mapping created before reasoning was stored.")
        return MappingRecord(
            id=model.id,
            dataset_name=model.dataset_name,
            mapping_json=MappingResult(**mapping_payload),
            confidence=model.confidence,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
