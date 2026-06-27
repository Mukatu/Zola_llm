"""Tests OPS-1 — Facility (échéancier) + HSE (cartographie, indicateurs) sur le store."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/ops.db")
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


async def test_facility_echeancier(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # échéance d'assurance dans 10 jours → doit être due (horizon 30)
        proche = (date.today() + timedelta(days=10)).isoformat()
        await ac.post(
            "/v1/erp/echeances",
            json={
                "id_externe": "EC1",
                "type_echeance": "assurance",
                "libelle": "Assurance flotte",
                "date_echeance": proche,
            },
        )
        # échéance lointaine → hors horizon
        loin = (date.today() + timedelta(days=120)).isoformat()
        await ac.post(
            "/v1/erp/echeances",
            json={
                "id_externe": "EC2",
                "type_echeance": "contrat",
                "libelle": "Bail",
                "date_echeance": loin,
            },
        )
        body = (await ac.get("/v1/erp/facility/echeancier?horizon_jours=30")).json()
        assert len(body["echeances"]) == 1
        assert body["echeances"][0]["reference"] == "EC1"


async def test_hse_cartographie_and_indicators(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/risques",
            json={
                "id_externe": "R1",
                "libelle": "Chute de hauteur",
                "probabilite": 4,
                "gravite": 5,
            },
        )
        carto = (await ac.get("/v1/erp/hse/cartographie")).json()["risques"]
        assert carto[0]["reference"] == "R1"
        assert carto[0]["criticite"] == 20  # 4 × 5
        assert carto[0]["niveau"] in ("eleve", "critique", "majeur", "moyen", "faible")

        await ac.post(
            "/v1/erp/incidents",
            json={
                "id_externe": "I1",
                "date_incident": "2026-06-01",
                "gravite": "grave",
                "jours_arret": 5,
            },
        )
        indic = (await ac.get("/v1/erp/hse/indicators?heures_travaillees=100000")).json()
        assert indic["statistiques"]["total"] == 1
