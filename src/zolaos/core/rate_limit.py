"""Rate limiting basé sur Redis (sliding window approximé par compteur fixe).

Phase 1 : limite par identifiant (clé d'API ou IP) avec fenêtre d'1 minute.
"""

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis_async

from zolaos.core.settings import Settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_seconds: int


class RedisRateLimiter:
    """Compteur fixe Redis avec TTL d'1 minute."""

    def __init__(self, redis_client: redis_async.Redis, per_minute: int) -> None:
        self._redis = redis_client
        self._limit = per_minute

    async def check(self, identifier: str) -> RateLimitResult:
        key = f"rl:{identifier}:{self._minute_window()}"
        pipe = self._redis.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, 60, nx=True)  # TTL posé uniquement à la création
        results = await pipe.execute()
        count = int(results[0])

        allowed = count <= self._limit
        remaining = max(0, self._limit - count)
        reset = 60 - (self._epoch_seconds() % 60)
        return RateLimitResult(allowed=allowed, remaining=remaining, reset_seconds=reset)

    @staticmethod
    def _minute_window() -> int:
        from time import time

        return int(time()) // 60

    @staticmethod
    def _epoch_seconds() -> int:
        from time import time

        return int(time())


def make_redis_client(settings: Settings) -> redis_async.Redis:
    return redis_async.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD.get_secret_value() or None,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
