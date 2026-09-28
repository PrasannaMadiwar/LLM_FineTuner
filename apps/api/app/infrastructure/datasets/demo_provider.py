import json
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from app.domain.datasets import DatasetMetadata, DatasetSearchResult, DatasetSource
from app.infrastructure.datasets.base import DatasetNotFoundError, DatasetProvider

DEMO_DATASET_ID = "builtin/edi-demo"
_DEMO_FILE = Path(__file__).with_name("demo_data") / "edi_demo.jsonl"
_SEARCH_KEYWORDS = ("demo", "builtin", "built-in", "edi", "sample", "offline")


@lru_cache
def _demo_rows() -> tuple[dict, ...]:
    with _DEMO_FILE.open(encoding="utf-8") as file:
        return tuple(json.loads(line) for line in file if line.strip())


class DemoDatasetProvider(DatasetProvider):
    """A small dataset bundled with the API, so a demo never depends on Hugging Face.

    It is served as raw instruction/output rows and goes through the same
    preview, mapping, validation and normalization steps as any remote dataset.
    """

    source = DatasetSource.DEMO

    async def search_datasets(self, query: str, limit: int) -> list[DatasetSearchResult]:
        if not any(keyword in query.lower() for keyword in _SEARCH_KEYWORDS):
            return []
        return [self._search_result()]

    async def get_dataset_info(self, dataset_id: str) -> DatasetMetadata:
        self._require_known(dataset_id)
        rows = _demo_rows()
        return DatasetMetadata(
            dataset_id=DEMO_DATASET_ID,
            name=DEMO_DATASET_ID,
            source=self.source,
            description=self._search_result().description,
            license="Generated for this project",
            size=len(rows),
            column_names=["instruction", "output"],
            splits=["train"],
            row_counts={"train": len(rows)},
            sample_rows=list(rows[:3]),
        )

    async def list_splits(self, dataset_id: str) -> list[str]:
        self._require_known(dataset_id)
        return ["train"]

    async def preview_dataset(self, dataset_id: str, split: str | None, limit: int) -> list[dict]:
        self._require_known(dataset_id)
        return list(_demo_rows()[:limit])

    async def iter_dataset_rows(
        self,
        dataset_id: str,
        split: str | None,
        batch_size: int,
    ) -> AsyncIterator[list[dict]]:
        self._require_known(dataset_id)
        rows = _demo_rows()
        for start in range(0, len(rows), batch_size):
            yield list(rows[start : start + batch_size])

    def _search_result(self) -> DatasetSearchResult:
        return DatasetSearchResult(
            dataset_id=DEMO_DATASET_ID,
            name="Built-in demo dataset",
            source=self.source,
            description=(
                f"{len(_demo_rows())} engineering and maths Q&A rows bundled with the app. "
                "Works offline and trains in a few minutes."
            ),
            size=len(_demo_rows()),
        )

    @staticmethod
    def _require_known(dataset_id: str) -> None:
        if dataset_id != DEMO_DATASET_ID:
            raise DatasetNotFoundError(f"Demo dataset '{dataset_id}' does not exist.")
