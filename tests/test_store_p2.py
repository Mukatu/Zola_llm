"""Tests P2 — persistance écritures (validées SYSCOHADA + balance vivante) et stocks.

SQLite (override de get_session). Réutilise les moteurs compta/supply existants.
"""

from __future__ import annotations

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


async def _make_client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/p2.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_journal_validated_and_living_balance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _make_client(tmp_path) as ac:
        # écriture équilibrée (411 / 701 + 4431) → 201
        r = await ac.post(
            "/v1/erp/journal",
            json={
                "date_ecriture": "2026-06-10",
                "journal": "VT",
                "libelle": "Vente",
                "lignes": [
                    {"compte": "411", "libelle": "Client", "debit_xaf": "1180"},
                    {"compte": "701", "libelle": "Vente", "credit_xaf": "1000"},
                    {"compte": "4431", "libelle": "TVA", "credit_xaf": "180"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["validation"]["ok"] is True
        assert r.json()["equilibre"] is True

        # écriture déséquilibrée → 422 (rejetée)
        r = await ac.post(
            "/v1/erp/journal",
            json={
                "date_ecriture": "2026-06-11",
                "journal": "VT",
                "libelle": "Bancale",
                "lignes": [
                    {"compte": "411", "libelle": "Client", "debit_xaf": "1000"},
                    {"compte": "701", "libelle": "Vente", "credit_xaf": "900"},
                ],
            },
        )
        assert r.status_code == 422

        # balance vivante : agrège l'unique écriture persistée
        r = await ac.get("/v1/erp/journal/balance")
        body = r.json()
        assert body["equilibre"] is True
        assert body["total_debit_xaf"] == "1180"
        comptes = {c["compte"]: c for c in body["comptes"]}
        assert comptes["411"]["debit_xaf"] == "1180"
        assert comptes["701"]["credit_xaf"] == "1000"


async def test_stock_crud_and_analyze(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _make_client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/stock",
            json={
                "sku": "MED-001",
                "libelle": "Paracétamol",
                "quantite_actuelle": "20",
                "conso_moyenne_jour": "5",
                "delai_appro_jours": 7,
                "stock_securite": "10",
            },
        )
        assert r.status_code == 201, r.text

        r = await ac.get("/v1/erp/stock")
        assert len(r.json()["items"]) == 1

        r = await ac.post("/v1/erp/stock/analyze")
        skus = {s["sku"] for s in r.json()["suggestions"]}
        assert "MED-001" in skus  # stock bas → réappro suggéré
