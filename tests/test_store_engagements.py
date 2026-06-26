"""Tests Achats v2 — engagements (chaîne EB→DA→BC) : CRUD + indicateurs déterministes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.engagements import Engagement, detect_alertes, engagement_stats, phase
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/eng.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


# ----------------------------------------------------------------- moteur (pur)


def test_phase_derivation() -> None:
    assert phase(Engagement(numero_eb="E1")) == "besoin"
    assert phase(Engagement(numero_eb="E1", numero_da="D1")) == "demande"
    assert phase(Engagement(numero_eb="E1", numero_da="D1", numero_bc="B1")) == "commande"
    assert phase(Engagement(numero_eb="E1", numero_bc="B1", statut_bc="Traité")) == "traite"
    assert phase(Engagement(numero_eb="E1", statut_ebda="OK / Annulée")) == "annulee"


def test_stats_transformation_and_ecart() -> None:
    engs = [
        Engagement(
            numero_eb="0001/26",
            numero_da="0001/26",
            numero_bc="0001/26",
            date_eb=date(2026, 4, 1),
            date_da=date(2026, 4, 6),
            date_bc=date(2026, 4, 16),
            direction="DFC",
            acheteur="Ferlez",
            estimation_xaf="1000000",
            montant_xaf="1200000",  # dépassement +200k
            statut_bc="Traité",
        ),
        Engagement(
            numero_eb="0002/26",
            numero_da="0002/26",
            direction="DOM",
            acheteur="Leroy",
            estimation_xaf="500000",
            statut_ebda="OK / En cours CDG",
        ),
        Engagement(numero_eb="0003/26", direction="DFC", acheteur="Ferlez"),
        Engagement(numero_eb="0004/26", statut_ebda="OK / Annulée"),  # exclu des actifs
    ]
    s = engagement_stats(engs)
    assert s.nb_total == 4
    assert s.par_phase == {"traite": 1, "demande": 1, "besoin": 1, "annulee": 1}
    # actifs = 3 (l'annulé est exclu) : EB=3, DA=2, BC=1
    assert (s.nb_eb, s.nb_da, s.nb_bc) == (3, 2, 1)
    assert str(s.taux_eb_vers_bc_pct) == "33.3"
    assert s.engage_total_xaf == 1200000  # seul l'engagement avec BC a un montant
    assert s.estimation_totale_xaf == 1500000
    assert s.ecart_xaf == -300000
    assert s.nb_depassements == 1
    # répartition par direction (DFC en tête sur l'engagé)
    assert s.par_direction[0].cle == "DFC"
    # délais moyens
    assert s.delai_moyen_eb_da_jours == 5
    assert s.delai_moyen_da_bc_jours == 10


def test_alertes_depassement_et_bloque() -> None:
    engs = [
        Engagement(numero_eb="0001/26", estimation_xaf="100", montant_xaf="150", numero_bc="B1"),
        Engagement(
            numero_eb="0002/26",
            date_eb=date(2026, 1, 1),
            date_da=date(2026, 1, 2),
            statut_ebda="OK / En cours CDG",
        ),
    ]
    alertes = detect_alertes(engs, as_of=date(2026, 6, 1))
    types = {a.type for a in alertes}
    assert "depassement" in types
    assert "bloque" in types


# ----------------------------------------------------------------- endpoints


async def test_engagement_crud_and_stats(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/engagements",
            json={
                "numero_eb": "0319/26",
                "numero_da": "0313/26",
                "numero_bc": "0172/26",
                "date_eb": "2026-04-13",
                "date_da": "2026-04-28",
                "date_bc": "2026-04-30",
                "direction": "DIP",
                "service": "SIPT",
                "demandeur": "BELO Dasthy",
                "acheteur": "Ferlez",
                "fournisseur": "HBM Services",
                "estimation_xaf": "200000",
                "montant_xaf": "225910",
                "statut_ebda": "OK / Traitée",
                "statut_bc": "Traité",
            },
        )
        assert r.status_code == 201, r.text
        eng_id = r.json()["id"]

        assert len((await ac.get("/v1/erp/engagements")).json()["engagements"]) == 1

        body = (await ac.get("/v1/erp/engagements/stats")).json()
        stats = body["stats"]
        assert stats["nb_total"] == 1
        assert stats["par_phase"]["traite"] == 1
        assert stats["nb_depassements"] == 1  # 225910 > 200000
        assert stats["par_acheteur"][0]["cle"] == "Ferlez"
        # dépassement remonté en alerte
        assert any(a["type"] == "depassement" for a in body["alertes"])

        # mise à jour de statut
        r = await ac.patch(f"/v1/erp/engagements/{eng_id}", json={"statut_bc": "Annulé"})
        assert r.json()["statut_bc"] == "Annulé"
