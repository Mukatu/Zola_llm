"""Collecte d'usage inter-box par le tunnel (facturation, déploiement hybride).

Couvre :
- set_usage_durable : ÉCRASE (SET) les totaux du jour (idempotent, pas d'addition)
- collect_local_usage (box) : agrège core.usage_daily par jour → {day, requests, tokens}
- ingest_reported_usage (cortex) : persiste sous le tenant donné ; jour invalide = no-op
- TunnelChannel.serve : une trame `usage_report` est ingérée sous l'identité du canal
- _usage_report_loop (box) : désactivé si USAGE_REPORT_SECONDS <= 0
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from zolaos.billing.collector import collect_local_usage, ingest_reported_usage
from zolaos.billing.ledger import record_usage_durable, set_usage_durable
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.tunnel.agent import _usage_report_loop
from zolaos.tunnel.channel import TunnelChannel

# Jour passé distinctif : isolé (aucun autre test ne l'utilise) → totaux exacts.
_PAST = date(2018, 6, 15)
_PAST_STR = "20180615"
_DAYS_BACK = (datetime.now(UTC).date() - _PAST).days + 1


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    reset_engine_cache()
    yield
    reset_engine_cache()


async def _cleanup(tenant_ids: list[str]) -> None:
    async with get_session_factory()() as s:
        for tid in tenant_ids:
            await s.execute(text("DELETE FROM core.usage_daily WHERE tenant_id = :t"), {"t": tid})
        await s.commit()


# ----------------------------------------------------------------------------
# set_usage_durable : écrasement
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_set_usage_durable_overwrites() -> None:
    tid = "set-" + uuid.uuid4().hex[:8]
    async with get_session_factory()() as s:
        await set_usage_durable(s, tenant_id=tid, day=_PAST, requests=5, tokens=50)
        await set_usage_durable(s, tenant_id=tid, day=_PAST, requests=3, tokens=30)
        await s.commit()
    try:
        async with get_session_factory()() as s:
            row = (
                await s.execute(
                    text("SELECT requests, tokens FROM core.usage_daily WHERE tenant_id = :t"),
                    {"t": tid},
                )
            ).first()
        assert tuple(row) == (3, 30)  # dernière valeur (SET), pas 8/80
    finally:
        await _cleanup([tid])


# ----------------------------------------------------------------------------
# collect_local_usage
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_collect_local_usage_aggregates_day() -> None:
    a, b = "loc-a-" + uuid.uuid4().hex[:6], "loc-b-" + uuid.uuid4().hex[:6]
    async with get_session_factory()() as s:
        # Deux tenants locaux, même jour → collect somme par jour (tous tenants).
        await record_usage_durable(s, tenant_id=a, day=_PAST, requests=2, tokens=20)
        await record_usage_durable(s, tenant_id=b, day=_PAST, requests=3, tokens=30)
        await s.commit()
    try:
        reports = await collect_local_usage(days=_DAYS_BACK)
        mine = next((r for r in reports if r["day"] == _PAST_STR), None)
        assert mine is not None
        assert mine["requests"] == 5  # 2 + 3
        assert mine["tokens"] == 50
    finally:
        await _cleanup([a, b])


# ----------------------------------------------------------------------------
# ingest_reported_usage
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ingest_reported_usage_sets_and_is_idempotent() -> None:
    tid = "ing-" + uuid.uuid4().hex[:8]
    try:
        await ingest_reported_usage(tid, day=_PAST_STR, requests=42, tokens=100)
        await ingest_reported_usage(tid, day=_PAST_STR, requests=50, tokens=120)  # ré-rapport
        async with get_session_factory()() as s:
            row = (
                await s.execute(
                    text("SELECT requests, tokens FROM core.usage_daily WHERE tenant_id = :t"),
                    {"t": tid},
                )
            ).first()
        assert tuple(row) == (50, 120)  # écrasé, pas cumulé (92/220)
    finally:
        await _cleanup([tid])


@pytest.mark.asyncio
async def test_ingest_reported_usage_bad_day_is_noop() -> None:
    tid = "bad-" + uuid.uuid4().hex[:8]
    await ingest_reported_usage(tid, day="pas-une-date", requests=1, tokens=1)  # ne lève pas
    async with get_session_factory()() as s:
        row = (
            await s.execute(text("SELECT 1 FROM core.usage_daily WHERE tenant_id = :t"), {"t": tid})
        ).first()
    assert row is None  # rien persisté


# ----------------------------------------------------------------------------
# TunnelChannel : ingestion d'un usage_report sous l'identité du canal
# ----------------------------------------------------------------------------
class _FakeWS:
    def __init__(self, incoming: list[str]) -> None:
        self.incoming = list(incoming)
        self.sent: list[str] = []

    async def receive_text(self) -> str:
        if self.incoming:
            return self.incoming.pop(0)
        raise RuntimeError("stop")

    async def send_text(self, msg: str) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_channel_ingests_usage_report_under_channel_tenant() -> None:
    box_tid = "chan-" + uuid.uuid4().hex[:8]
    frame = json.dumps({"type": "usage_report", "day": _PAST_STR, "requests": 11, "tokens": 111})
    try:
        channel = TunnelChannel(box_tid, _FakeWS([frame]))
        with pytest.raises(RuntimeError):
            await channel.serve()
        async with get_session_factory()() as s:
            row = (
                await s.execute(
                    text("SELECT requests, tokens FROM core.usage_daily WHERE tenant_id = :t"),
                    {"t": box_tid},
                )
            ).first()
        assert tuple(row) == (11, 111)  # persisté sous l'identité du canal
    finally:
        await _cleanup([box_tid])


# ----------------------------------------------------------------------------
# _usage_report_loop désactivé
# ----------------------------------------------------------------------------
class _SendWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, msg: str) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_usage_report_loop_disabled_without_interval() -> None:
    ws = _SendWS()
    await _usage_report_loop(ws, SimpleNamespace(USAGE_REPORT_SECONDS=0.0))
    assert ws.sent == []  # rend la main, aucun rapport
