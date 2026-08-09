from collections.abc import AsyncIterator

import httpx

from app.domain.datasets import DatasetMetadata, DatasetSearchResult, DatasetSource
from app.infrastructure.datasets.base import (
    DatasetNotFoundError,
    DatasetProvider,
    DatasetProviderError,
)


class HuggingFaceDatasetProvider(DatasetProvider):
    source = DatasetSource.HUGGING_FACE

    def __init__(self, base_url: str = "https://huggingface.co"):
        self._base_url = base_url.rstrip("/")
        self._datasets_server_url = "https://datasets-server.huggingface.co"

    async def search_datasets(self, query: str, limit: int) -> list[DatasetSearchResult]:
        params = {"search": query, "limit": limit, "full": "true"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self._base_url}/api/datasets", params=params)
            response.raise_for_status()
        return [self._to_search_result(item) for item in response.json()]

    async def get_dataset_info(self, dataset_id: str) -> DatasetMetadata:
        async with httpx.AsyncClient(timeout=20) as client:
            dataset_response = await client.get(f"{self._base_url}/api/datasets/{dataset_id}")
            self._raise_for_dataset_response(dataset_response, dataset_id)
            splits = await self._fetch_splits(client, dataset_id)
            rows = await self.preview_dataset(dataset_id, splits[0] if splits else None, 10)

        dataset = dataset_response.json()
        card_data = dataset.get("cardData") or {}
        features = self._extract_features(dataset)
        column_names = list(features.keys())
        row_counts = self._extract_row_counts(dataset)

        return DatasetMetadata(
            dataset_id=dataset_id,
            name=dataset.get("id") or dataset_id,
            source=self.source,
            description=card_data.get("pretty_name") or dataset.get("description"),
            license=self._extract_license(dataset),
            size=dataset.get("usedStorage"),
            features=features,
            column_names=column_names,
            splits=splits,
            row_counts=row_counts,
            sample_rows=rows,
        )

    async def list_splits(self, dataset_id: str) -> list[str]:
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._fetch_splits(client, dataset_id)

    async def preview_dataset(self, dataset_id: str, split: str | None, limit: int) -> list[dict]:
        params = {"dataset": dataset_id, "config": "default", "split": split or "train"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self._datasets_server_url}/first-rows", params=params)
            if response.status_code == 400 and params["config"] == "default":
                configs = await self._fetch_configs(client, dataset_id)
                if configs:
                    params["config"] = configs[0]
                    response = await client.get(
                        f"{self._datasets_server_url}/first-rows",
                        params=params,
                    )
            self._raise_for_dataset_response(response, dataset_id)
        rows = response.json().get("rows", [])
        return [row.get("row", {}) for row in rows[:limit]]

    async def iter_dataset_rows(
        self,
        dataset_id: str,
        split: str | None,
        batch_size: int,
    ) -> AsyncIterator[list[dict]]:
        offset = 0
        config = "default"
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                params = {
                    "dataset": dataset_id,
                    "config": config,
                    "split": split or "train",
                    "offset": offset,
                    "length": batch_size,
                }
                response = await client.get(f"{self._datasets_server_url}/rows", params=params)
                if response.status_code == 400 and config == "default":
                    configs = await self._fetch_configs(client, dataset_id)
                    if configs:
                        config = configs[0]
                        continue
                self._raise_for_dataset_response(response, dataset_id)
                rows = [row.get("row", {}) for row in response.json().get("rows", [])]
                if not rows:
                    break
                yield rows
                offset += len(rows)

    async def _fetch_splits(self, client: httpx.AsyncClient, dataset_id: str) -> list[str]:
        response = await client.get(f"{self._datasets_server_url}/splits", params={"dataset": dataset_id})
        if response.status_code >= 400:
            return []
        return sorted({item.get("split") for item in response.json().get("splits", []) if item.get("split")})

    async def _fetch_configs(self, client: httpx.AsyncClient, dataset_id: str) -> list[str]:
        response = await client.get(f"{self._datasets_server_url}/splits", params={"dataset": dataset_id})
        if response.status_code >= 400:
            return []
        return sorted({item.get("config") for item in response.json().get("splits", []) if item.get("config")})

    def _to_search_result(self, item: dict) -> DatasetSearchResult:
        return DatasetSearchResult(
            dataset_id=item.get("id") or item.get("_id") or "",
            name=item.get("id") or item.get("_id") or "",
            source=self.source,
            description=item.get("description"),
            license=self._extract_license(item),
            size=item.get("usedStorage"),
            downloads=item.get("downloads"),
            likes=item.get("likes"),
        )

    @staticmethod
    def _extract_license(dataset: dict) -> str | None:
        card_data = dataset.get("cardData") or {}
        license_value = card_data.get("license") or dataset.get("license")
        if isinstance(license_value, list):
            return ", ".join(str(item) for item in license_value)
        return str(license_value) if license_value else None

    @staticmethod
    def _extract_features(dataset: dict) -> dict:
        siblings = dataset.get("siblings") or []
        card_data = dataset.get("cardData") or {}
        features = card_data.get("features")
        if isinstance(features, dict):
            return features
        if isinstance(features, list):
            return {str(item.get("name")): item for item in features if isinstance(item, dict) and item.get("name")}
        return {"files": [item.get("rfilename") for item in siblings if item.get("rfilename")]}

    @staticmethod
    def _extract_row_counts(dataset: dict) -> dict[str, int]:
        card_data = dataset.get("cardData") or {}
        dataset_info = card_data.get("dataset_info") or {}
        splits = dataset_info.get("splits") or {}
        if isinstance(splits, dict):
            return {
                split: int(info.get("num_examples", 0))
                for split, info in splits.items()
                if isinstance(info, dict)
            }
        return {}

    @staticmethod
    def _raise_for_dataset_response(response: httpx.Response, dataset_id: str) -> None:
        if response.status_code == 404:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.", status_code=404)
        if response.status_code in {400, 422}:
            raise DatasetProviderError("Hugging Face rejected the dataset request.", status_code=response.status_code)
        if response.status_code >= 500:
            raise DatasetProviderError("Hugging Face dataset service is unavailable.", status_code=response.status_code)
        response.raise_for_status()
