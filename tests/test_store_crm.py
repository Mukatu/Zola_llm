"""Tests P2b — CRM persisté : CRUD, kanban, interactions, analyse/forecast, conversion.

SQLite (override de get_session). Réutilise le moteur CRM existant sur le store.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/crm.db")
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


async def test_customer_opportunity_quote_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/crm/customers",
            json={"id_externe": "C1", "nom": "ACME", "type": "client", "source": "referral"},
        )
        assert r.status_code == 201, r.text
        assert (await ac.get("/v1/crm/customers")).json()["customers"][0]["nom"] == "ACME"

        r = await ac.post(
            "/v1/crm/opportunities",
            json={
                "id_externe": "O1",
                "client": "ACME",
                "libelle": "Projet X",
                "montant_xaf": "5000000",
                "etape": "qualification",
            },
        )
        assert r.status_code == 201, r.text
        opp_id = r.json()["id"]
        assert len((await ac.get("/v1/crm/opportunities")).json()["opportunities"]) == 1

        r = await ac.post(
            "/v1/crm/quotes",
            json={
                "id_externe": "Q1",
                "numero": "DV-001",
                "client": "ACME",
                "date_emission": "2026-06-01",
                "statut": "brouillon",
                "lignes": [{"libelle": "Presta", "montant_ht_xaf": "1000000"}],
                "montant_ht_xaf": "1000000",
                "montant_ttc_xaf": "1180000",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["lignes"][0]["libelle"] == "Presta"

        # kanban : déplacement d'étape persisté
        r = await ac.patch(f"/v1/crm/opportunities/{opp_id}/stage", json={"etape": "negociation"})
        assert r.json()["etape"] == "negociation"


async def test_interaction_updates_recency_and_analyze(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/crm/customers",
            json={"id_externe": "C1", "nom": "ACME", "source": "referral"},
        )
        opp_id = (
            await ac.post(
                "/v1/crm/opportunities",
                json={
                    "id_externe": "O1",
                    "client": "ACME",
                    "libelle": "Projet X",
                    "montant_xaf": "5000000",
                    "etape": "negociation",
                },
            )
        ).json()["id"]

        # interaction récente → propage derniere_interaction + sert au scoring
        r = await ac.post(
            "/v1/crm/interactions",
            json={"opportunity_id": opp_id, "type": "appel", "date": "2026-06-25", "resume": "RDV"},
        )
        assert r.status_code == 201, r.text
        assert (await ac.get("/v1/crm/opportunities")).json()["opportunities"][0][
            "derniere_interaction"
        ] == "2026-06-25"

        body = (await ac.get("/v1/crm/analyze")).json()
        assert body["pipeline"]["nb_open"] == 1
        score = body["scores"][opp_id]
        # source referral (1.0) prise en compte dans les raisons
        assert any("referral" in r for r in score["raisons"])
        assert score["grade"] in ("A", "B")


async def test_forecast_by_month(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        for i, (montant, mois) in enumerate([("4000000", "2026-07-15"), ("2000000", "2026-07-20")]):
            await ac.post(
                "/v1/crm/opportunities",
                json={
                    "id_externe": f"O{i}",
                    "client": "ACME",
                    "libelle": "X",
                    "montant_xaf": montant,
                    "etape": "negociation",  # prob 0.80
                    "date_cloture_prevue": mois,
                },
            )
        body = (await ac.get("/v1/crm/forecast")).json()
        juillet = next(p for p in body["prevision"] if p["mois"] == "2026-07")
        assert juillet["brut_xaf"] == "6000000"
        assert juillet["pondere_xaf"] == "4800000"  # (4M+2M)*0.8


async def test_quote_convert_to_invoice(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        quote_id = (
            await ac.post(
                "/v1/crm/quotes",
                json={
                    "id_externe": "Q1",
                    "numero": "DV-001",
                    "client": "ACME",
                    "date_emission": "2026-06-01",
                    "statut": "accepte",
                    "lignes": [{"libelle": "Presta", "montant_ht_xaf": "1000000"}],
                    "montant_ht_xaf": "1000000",
                    "montant_ttc_xaf": "1180000",
                },
            )
        ).json()["id"]

        r = await ac.post(f"/v1/crm/quotes/{quote_id}/convert")
        assert r.status_code == 200, r.text
        assert r.json()["invoice"]["numero"] == "DV-001"
        # la facture est bien dans le registre Compta (clôture continue)
        invs = (await ac.get("/v1/erp/invoices")).json()["invoices"]
        assert len(invs) == 1 and invs[0]["montant_ttc_xaf"] == "1180000.00"

        # double conversion → 409
        r = await ac.post(f"/v1/crm/quotes/{quote_id}/convert")
        assert r.status_code == 409


async def test_quote_convert_refused_when_not_accepted(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        quote_id = (
            await ac.post(
                "/v1/crm/quotes",
                json={
                    "id_externe": "Q2",
                    "numero": "DV-002",
                    "client": "ACME",
                    "date_emission": "2026-06-01",
                    "statut": "envoye",
                    "montant_ht_xaf": "500000",
                    "montant_ttc_xaf": "590000",
                },
            )
        ).json()["id"]
        r = await ac.post(f"/v1/crm/quotes/{quote_id}/convert")
        assert r.status_code == 422
