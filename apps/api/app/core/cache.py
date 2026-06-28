from redis.asyncio import Redis

from app.core.config import get_settings


def create_redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def ping_redis() -> bool:
    client = create_redis_client()
    try:
        return bool(await client.ping())
    finally:
        await client.aclose()
