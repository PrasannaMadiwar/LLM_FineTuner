from abc import ABC, abstractmethod

from app.domain.datasets import DatasetMetadata, DatasetSearchResult, DatasetSource


class DatasetProvider(ABC):
    source: DatasetSource

    @abstractmethod
    async def search_datasets(self, query: str, limit: int) -> list[DatasetSearchResult]:
        raise NotImplementedError

    @abstractmethod
    async def get_dataset_info(self, dataset_id: str) -> DatasetMetadata:
        raise NotImplementedError

    @abstractmethod
    async def list_splits(self, dataset_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def preview_dataset(self, dataset_id: str, split: str | None, limit: int) -> list[dict]:
        raise NotImplementedError
