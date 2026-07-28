"""Tests du metering d'usage + quotas (`zolaos.core.metering`).

Aucun Redis réel : un faux client in-memory (dict + incr/expire/get async)
tient lieu de `RedisLike`. Zéro réseau.
"""

from __future__ import annotations

import pytest

from zolaos.core.metering import (
    QuotaExceeded,
    enforce_quota,
    get_usage,
    record_usage,
)


class FakeRedis:
    """Faux client Redis async : dict en mémoire, sans réseau ni process externe."""

    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, name: str, amount: int = 1) -> int:
        self.store[name] = self.store.get(name, 0) + amount
        return self.store[name]

    async def expire(self, name: str, time: int) -> bool:
        self.ttls[name] = time
        return True

    async def get(self, name: str) -> str | None:
        value = self.store.get(name)
        return str(value) if value is not None else None


DAY = "20260728"


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.mark.asyncio
async def test_record_usage_increments_requests_and_tokens(redis: FakeRedis) -> None:
    await record_usage(redis, key_id="key-a", tokens=100, day=DAY)
    await record_usage(redis, key_id="key-a", tokens=50, day=DAY)

    usage = await get_usage(redis, key_id="key-a", day=DAY)
    assert usage == {"requests": 2, "tokens": 150}


@pytest.mark.asyncio
async def test_record_usage_without_tokens_only_bumps_requests(redis: FakeRedis) -> None:
    await record_usage(redis, key_id="key-b", day=DAY)

    usage = await get_usage(redis, key_id="key-b", day=DAY)
    assert usage == {"requests": 1, "tokens": 0}


@pytest.mark.asyncio
async def test_record_usage_sets_a_ttl_on_counters(redis: FakeRedis) -> None:
    await record_usage(redis, key_id="key-c", tokens=10, day=DAY)

    assert redis.ttls[f"usage:key-c:{DAY}:req"] == 40 * 24 * 3600
    assert redis.ttls[f"usage:key-c:{DAY}:tok"] == 40 * 24 * 3600


@pytest.mark.asyncio
async def test_record_usage_keys_are_isolated_per_key_id_and_day(redis: FakeRedis) -> None:
    await record_usage(redis, key_id="key-d", tokens=5, day=DAY)
    await record_usage(redis, key_id="key-e", tokens=7, day=DAY)
    await record_usage(redis, key_id="key-d", tokens=1, day="20260729")

    assert await get_usage(redis, key_id="key-d", day=DAY) == {"requests": 1, "tokens": 5}
    assert await get_usage(redis, key_id="key-e", day=DAY) == {"requests": 1, "tokens": 7}
    assert await get_usage(redis, key_id="key-d", day="20260729") == {
        "requests": 1,
        "tokens": 1,
    }


@pytest.mark.asyncio
async def test_get_usage_empty_day_returns_zeroes(redis: FakeRedis) -> None:
    usage = await get_usage(redis, key_id="never-used", day=DAY)
    assert usage == {"requests": 0, "tokens": 0}


@pytest.mark.asyncio
async def test_enforce_quota_raises_once_quota_reached(redis: FakeRedis) -> None:
    quota = 3
    for _ in range(quota):
        # En dessous du quota : jamais de blocage.
        await enforce_quota(redis, key_id="key-f", daily_request_quota=quota)
        await record_usage(redis, key_id="key-f")

    # Le compteur de requêtes vaut désormais `quota` : la prochaine requête doit être bloquée.
    with pytest.raises(QuotaExceeded):
        await enforce_quota(redis, key_id="key-f", daily_request_quota=quota)


@pytest.mark.asyncio
async def test_enforce_quota_none_is_unlimited(redis: FakeRedis) -> None:
    for _ in range(1000):
        await record_usage(redis, key_id="key-g")

    # Ne doit jamais lever, quel que soit le volume déjà consommé.
    await enforce_quota(redis, key_id="key-g", daily_request_quota=None)


@pytest.mark.asyncio
async def test_enforce_quota_zero_is_unlimited(redis: FakeRedis) -> None:
    for _ in range(1000):
        await record_usage(redis, key_id="key-h")

    # 0 = illimité, au même titre que None (cf. `ENGINE_DAILY_REQUEST_QUOTA`).
    await enforce_quota(redis, key_id="key-h", daily_request_quota=0)


@pytest.mark.asyncio
async def test_enforce_quota_does_not_consume_usage(redis: FakeRedis) -> None:
    """`enforce_quota` ne fait qu'une lecture : elle n'incrémente rien elle-même."""
    await enforce_quota(redis, key_id="key-i", daily_request_quota=10)
    usage = await get_usage(redis, key_id="key-i", day=_today_for_test())
    assert usage == {"requests": 0, "tokens": 0}


def _today_for_test() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y%m%d")
