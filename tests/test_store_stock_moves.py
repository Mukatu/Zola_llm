"""Tests STOCK-1 — mouvements de stock : valorisation PMP (moteur) + endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.inventory import StockInsuffisant, appliquer_mouvement
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/stock.db")
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


def test_pmp_entree_moyenne_ponderee() -> None:
    # 10 @ 100, puis 10 @ 200 → PMP = 150, qté 20
    r1 = appliquer_mouvement(
        type="entree",
        quantite=Decimal("10"),
        quantite_actuelle=Decimal("0"),
        pmp_actuel=Decimal("0"),
        cout_unitaire=Decimal("100"),
    )
    assert r1.nouvelle_quantite == Decimal("10.000")
    assert r1.nouveau_pmp_xaf == Decimal("100.00")
    r2 = appliquer_mouvement(
        type="entree",
        quantite=Decimal("10"),
        quantite_actuelle=Decimal("10"),
        pmp_actuel=Decimal("100"),
        cout_unitaire=Decimal("200"),
    )
    assert r2.nouvelle_quantite == Decimal("20.000")
    assert r2.nouveau_pmp_xaf == Decimal("150.00")


def test_sortie_au_pmp_et_insuffisance() -> None:
    r = appliquer_mouvement(
        type="sortie",
        quantite=Decimal("5"),
        quantite_actuelle=Decimal("20"),
        pmp_actuel=Decimal("150"),
    )
    assert r.nouvelle_quantite == Decimal("15.000")
    assert r.valeur_mouvement_xaf == Decimal("750.00")  # 5 * 150
    assert r.nouveau_pmp_xaf == Decimal("150.00")  # inchangé

    try:
        appliquer_mouvement(
            type="sortie",
            quantite=Decimal("100"),
            quantite_actuelle=Decimal("15"),
            pmp_actuel=Decimal("150"),
        )
        raise AssertionError("attendu StockInsuffisant")
    except StockInsuffisant:
        pass


# ----------------------------------------------------------------- endpoints


async def test_stock_move_validate_updates_item(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock",
            json={"sku": "SKU1", "libelle": "Vis", "quantite_actuelle": "0"},
        )

        # entrée 10 @ 100 (brouillon puis validée)
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-001",
                    "type": "entree",
                    "sku": "SKU1",
                    "quantite": "10",
                    "cout_unitaire_xaf": "100",
                    "date_mouvement": "2026-06-01",
                },
            )
        ).json()
        assert mv["statut"] == "brouillon"
        r = await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")
        assert r.status_code == 200, r.text
        art = r.json()["article"]
        assert art["quantite_actuelle"] == "10.000"
        assert art["pmp_xaf"] == "100.00"
        assert art["valeur_stock_xaf"] == "1000.00"

        # double validation → 409
        assert (await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")).status_code == 409

        # entrée 10 @ 200 → PMP 150, stock valorisé 3000
        mv2 = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-002",
                    "type": "entree",
                    "sku": "SKU1",
                    "quantite": "10",
                    "cout_unitaire_xaf": "200",
                    "date_mouvement": "2026-06-02",
                },
            )
        ).json()
        art2 = (await ac.post(f"/v1/erp/stock-moves/{mv2['id']}/validate")).json()["article"]
        assert art2["pmp_xaf"] == "150.00"
        assert art2["valeur_stock_xaf"] == "3000.00"


async def test_sortie_insuffisante_rejetee(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/stock",
            json={"sku": "SKU2", "libelle": "Boulon", "quantite_actuelle": "0"},
        )
        mv = (
            await ac.post(
                "/v1/erp/stock-moves",
                json={
                    "reference": "MV-003",
                    "type": "sortie",
                    "sku": "SKU2",
                    "quantite": "5",
                    "date_mouvement": "2026-06-03",
                },
            )
        ).json()
        assert (await ac.post(f"/v1/erp/stock-moves/{mv['id']}/validate")).status_code == 422
