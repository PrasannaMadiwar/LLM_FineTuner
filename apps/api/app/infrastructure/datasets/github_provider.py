from app.domain.datasets import DatasetMetadata, DatasetSearchResult, DatasetSource
from app.infrastructure.datasets.base import DatasetProvider


class GitHubDatasetProvider(DatasetProvider):
    source = DatasetSource.GITHUB

    async def search_datasets(self, query: str, limit: int) -> list[DatasetSearchResult]:
        return []

    async def get_dataset_info(self, dataset_id: str) -> DatasetMetadata:
        raise NotImplementedError("GitHub dataset metadata extraction is not implemented yet.")

    async def list_splits(self, dataset_id: str) -> list[str]:
        return []

    async def preview_dataset(self, dataset_id: str, split: str | None, limit: int) -> list[dict]:
        raise NotImplementedError("GitHub dataset preview is not implemented yet.")
