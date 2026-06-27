"""Tests BI — cockpit transversal agrégé sur le store (assembleur + endpoint)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.bi.kpi import dashboard_kpis
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/bi.db")
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


def test_dashboard_kpis_assemble() -> None:
    kpis = dashboard_kpis(
        ca_ht=Decimal("1000000"),
        marge_brute_xaf=Decimal("400000"),
        encours_clients_xaf=Decimal("250000"),
        encours_fournisseurs_xaf=Decimal("120000"),
        dso=Decimal("30"),
        position_tresorerie_xaf=Decimal("800000"),
        valeur_stock_xaf=Decimal("600000"),
        pipeline_pondere_xaf=Decimal("3000000"),
        engage_achats_xaf=Decimal("450000"),
        effectif_actif=12,
        masse_salariale_xaf=Decimal("3600000"),
    )
    by_code = {k.code: k for k in kpis}
    assert by_code["ca_ht"].valeur == Decimal("1000000")
    assert by_code["effectif"].valeur == Decimal("12")
    assert by_code["effectif"].unite == "unité"
    # couvre les domaines transversaux
    assert {k.domaine for k in kpis} >= {"commercial", "finance", "achats", "supply", "rh"}


async def test_dashboard_endpoint_aggregates_store(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # une vente, un compte + encaissement réalisé, un article de stock valorisé
        await ac.post(
            "/v1/erp/invoices",
            json={
                "numero": "FV-1",
                "tiers": "ACME",
                "date_emission": "2026-06-01",
                "montant_ht_xaf": "1000000",
                "montant_ttc_xaf": "1180000",
            },
        )
        await ac.post(
            "/v1/erp/bank-accounts",
            json={"code": "BNK", "libelle": "BGFI", "solde_initial_xaf": "500000"},
        )
        await ac.post(
            "/v1/erp/cash-flows",
            json={
                "reference": "ENC-1",
                "compte_code": "BNK",
                "sens": "encaissement",
                "montant_xaf": "300000",
                "date_operation": "2026-06-10",
                "statut": "realise",
            },
        )
        item = (
            await ac.post(
                "/v1/erp/stock",
                json={"sku": "S1", "libelle": "Vis", "quantite_actuelle": "0"},
            )
        ).json()
        assert item["sku"] == "S1"
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV",
                    "type": "entree",
                    "sku": "S1",
                    "quantite": "10",
                    "cout_unitaire_xaf": "1000",
                    "date_mouvement": "2026-06-02",
                },
            )
        ).json()
        await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")

        kpis = (await ac.get("/v1/bi/dashboard")).json()["kpis"]
        by = {k["code"]: k for k in kpis}
        assert by["ca_ht"]["valeur"] == "1000000"
        assert by["position_tresorerie"]["valeur"] == "800000"  # 500k + 300k
        assert by["valeur_stock"]["valeur"] == "10000"  # 10 * 1000
