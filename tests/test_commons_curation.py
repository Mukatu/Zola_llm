"""Commons Phase B — garde k-anonymat + curation (SQLite async en mémoire)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from zolaos.commons import curation
from zolaos.commons.pipeline import run_extraction, set_optin
from zolaos.db.store_models import AgentFeedbackRecord, ContribCandidate, StoreBase


async def _make():  # type: ignore[no-untyped-def]
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _contribue(session, tenant: str, query: str, reponse: str = "Trois mois.") -> None:  # type: ignore[no-untyped-def]
    await set_optin(session, tenant, enabled=True, scopes=["legal"])
    session.add(
        AgentFeedbackRecord(
            tenant_id=tenant, agent="legal.ohada", query=query, response=reponse, verdict="up"
        )
    )
    await session.commit()
    await run_extraction(session, tenant)
    await session.commit()


def test_is_eligible() -> None:
    c = ContribCandidate(type="qa", payload={}, content_hash="h", occurrences=3, status="pending")
    assert curation.is_eligible(c)
    c.occurrences = 2
    assert not curation.is_eligible(c)  # sous le seuil k=3
    c.occurrences = 3
    c.status = "validated"
    assert not curation.is_eligible(c)  # déjà traité


async def test_k_anonymat_gate() -> None:
    engine, sm = await _make()
    async with sm() as s:
        q = "Quel est le preavis pour un cadre ?"
        for tenant in ("A", "B"):
            await _contribue(s, tenant, q)
        cands = await curation.list_candidates(s, eligible_only=False)
        assert len(cands) == 1 and cands[0].occurrences == 2
        assert not curation.is_eligible(cands[0])  # 2 origines < 3
        assert await curation.list_candidates(s, eligible_only=True) == []

        await _contribue(s, "C", q)  # 3e origine distincte
        cands = await curation.list_candidates(s, eligible_only=False)
        assert cands[0].occurrences == 3 and curation.is_eligible(cands[0])
        assert len(await curation.list_candidates(s, eligible_only=True)) == 1
    await engine.dispose()


async def test_meme_tenant_une_seule_origine() -> None:
    engine, sm = await _make()
    async with sm() as s:
        await set_optin(s, "A", enabled=True, scopes=["legal"])
        for _ in range(2):
            s.add(
                AgentFeedbackRecord(
                    tenant_id="A", agent="legal.ohada", query="Meme question ?",
                    response="Meme reponse.", verdict="up",
                )
            )
        await s.commit()
        await run_extraction(s, "A")
        await s.commit()
        cands = await curation.list_candidates(s, eligible_only=False)
        assert len(cands) == 1 and cands[0].occurrences == 1  # 2 retours, 1 origine
    await engine.dispose()


async def test_validate_requiert_eligibilite() -> None:
    engine, sm = await _make()
    async with sm() as s:
        c = ContribCandidate(
            type="qa", domaine="legal", payload={"x": "y"}, content_hash="h1",
            origins=["o1"], occurrences=1,
        )
        s.add(c)
        await s.commit()
        with pytest.raises(ValueError):
            await curation.validate(s, c.id, by="cur@x.cg")  # 1 < 3

        c.occurrences = 3
        await s.commit()
        out = await curation.validate(s, c.id, by="cur@x.cg")
        assert out.status == "validated" and out.validated_by == "cur@x.cg"
        with pytest.raises(ValueError):
            await curation.validate(s, c.id, by="cur@x.cg")  # déjà validé
    await engine.dispose()


async def test_reject() -> None:
    engine, sm = await _make()
    async with sm() as s:
        c = ContribCandidate(type="qa", payload={}, content_hash="h2", occurrences=1)
        s.add(c)
        await s.commit()
        out = await curation.reject(s, c.id, by="cur@x.cg")
        assert out.status == "rejected"
    await engine.dispose()
