"""Commons Phase C — promotion des candidats validés (ingest mocké, SQLite async)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from zolaos.commons import promotion
from zolaos.db.store_models import CommonsAudit, ContribCandidate, StoreBase


async def _make():  # type: ignore[no-untyped-def]
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_promote_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    async def fake_ingest(**kw):  # type: ignore[no-untyped-def]
        calls.append(kw)
        return 1

    monkeypatch.setattr(promotion, "ingest_text", fake_ingest)

    engine, sm = await _make()
    async with sm() as s:
        s.add(
            ContribCandidate(
                type="qa", domaine="legal.ohada", payload={"question": "q", "reponse": "r"},
                content_hash="h1", occurrences=3, status="validated", validated_by="cur@x.cg",
            )
        )
        s.add(
            ContribCandidate(
                type="qa", payload={}, content_hash="h2", occurrences=1, status="pending"
            )
        )
        await s.commit()

        res = await promotion.promote_validated(s)
        await s.commit()

        assert res["promus"] == 1 and res["rag_commons"] == 1
        # ingéré dans le bon corpus, tagué contribution
        assert calls and calls[0]["schema"] == "rag_commons"
        assert "source:contribution" in calls[0]["tags"]

        promoted = (
            await s.execute(select(ContribCandidate).where(ContribCandidate.content_hash == "h1"))
        ).scalar_one()
        assert promoted.status == "promoted"

        pending = (
            await s.execute(select(ContribCandidate).where(ContribCandidate.content_hash == "h2"))
        ).scalar_one()
        assert pending.status == "pending"  # non validé → non promu

        audits = (await s.execute(select(CommonsAudit))).scalars().all()
        assert len(audits) == 1 and audits[0].content_hash == "h1"
        assert audits[0].validated_by == "cur@x.cg"  # traçabilité (anonyme, pas de tenant)
    await engine.dispose()
