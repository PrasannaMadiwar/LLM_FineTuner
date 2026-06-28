import json

from redis.asyncio import Redis

from app.domain.datasets import MappingResult


class MappingCache:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 86400):
        self._redis_client = redis_client
        self._ttl_seconds = ttl_seconds

    async def get(self, dataset_name: str) -> MappingResult | None:
        payload = await self._redis_client.get(self._key(dataset_name))
        if not payload:
            return None
        return MappingResult(**json.loads(payload))

    async def set(self, dataset_name: str, mapping: MappingResult) -> None:
        await self._redis_client.set(
            self._key(dataset_name),
            mapping.model_dump_json(),
            ex=self._ttl_seconds,
        )

    @staticmethod
    def _key(dataset_name: str) -> str:
        return f"dataset:mapping:{dataset_name}"
