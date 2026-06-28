from abc import ABC, abstractmethod

from app.domain.datasets import DatasetMetadata, LLMProviderError, MappingResult


class LLMProviderException(Exception):
    def __init__(self, error: LLMProviderError):
        super().__init__(error.message)
        self.error = error


class LLMProvider(ABC):
    @abstractmethod
    async def analyze_dataset(self, dataset_metadata: DatasetMetadata) -> MappingResult:
        raise NotImplementedError
