"""Règles apprises déterministes (multi-métier) — clé, lookup, capture, promotion."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from zolaos.agents.erp.categorisation import suggest_accounts
from zolaos.agents.erp.compta import ChartOfAccounts
from zolaos.commons import learned, promotion
from zolaos.commons.pipeline import capture_categorisation, set_optin
from zolaos.db.store_models import ContribCandidate, LearnedRule, StoreBase


async def _make():  # type: ignore[no-untyped-def]
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_rule_key_normalise_et_anonymise() -> None:
    assert learned.normalize("  Loyer   BUREAU ") == "loyer bureau"
    # e-mail dans le libellé → anonymisé dans la clé
    assert "[EMAIL]" in learned.rule_key("Facture de jean@x.cg")


def test_suggest_priorise_regle_apprise() -> None:
    chart = ChartOfAccounts.load("cg")
    out = suggest_accounts("Loyer bureau", chart=chart, learned_comptes=["521"])
    assert out[0].compte == "521"
    assert "apprise" in out[0].raison.lower()


async def test_lookup_exact_et_sous_chaine() -> None:
    engine, sm = await _make()
    async with sm() as s:
        s.add(LearnedRule(domaine="erp.compta", cle=learned.rule_key("loyer bureau"), valeur="622"))
        await s.commit()
        assert [r.valeur for r in await learned.lookup(s, "erp.compta", "Loyer bureau")] == ["622"]
        # sous-chaîne : la clé apprise est contenue dans un libellé plus long
        assert [r.valeur for r in await learned.lookup(s, "erp.compta", "Loyer bureau mensuel")] == ["622"]
        assert await learned.lookup(s, "erp.compta", "Achat carburant") == []
    await engine.dispose()


async def test_capture_gatee_par_optin() -> None:
    engine, sm = await _make()
    async with sm() as s:
        # sans opt-in → rien
        res = await capture_categorisation(s, "A", libelle="Loyer", valeur="622")
        assert res["captured"] is False
        # opt-in erp → candidat categorisation en quarantaine
        await set_optin(s, "A", enabled=True, scopes=["erp"])
        res = await capture_categorisation(s, "A", libelle="Loyer bureau", valeur="622")
        assert res["captured"] is True
        c = (await s.execute(select(ContribCandidate))).scalars().one()
        assert c.type == "categorisation" and c.payload["valeur"] == "622"
        assert "tenant" not in c.payload  # anonyme
    await engine.dispose()


async def test_promotion_route_vers_learned_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_ingest(**kw):  # type: ignore[no-untyped-def]
        raise AssertionError("categorisation ne doit PAS passer par rag_commons")

    monkeypatch.setattr(promotion, "ingest_text", fake_ingest)

    engine, sm = await _make()
    async with sm() as s:
        s.add(
            ContribCandidate(
                type="categorisation", domaine="erp.compta",
                payload={"domaine": "erp.compta", "cle": "loyer bureau", "valeur": "622"},
                content_hash="cat1", occurrences=3, status="validated", validated_by="cur@x.cg",
            )
        )
        await s.commit()
        res = await promotion.promote_validated(s)
        await s.commit()
        assert res["promus"] == 1
        rule = (await s.execute(select(LearnedRule))).scalars().one()
        assert rule.domaine == "erp.compta" and rule.cle == "loyer bureau" and rule.valeur == "622"
    await engine.dispose()
