"""Tests Secrétariat sociétaire — CRUD mandats/résolutions + échéancier légal."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/secretariat.db")
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


async def test_mandate_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        created = (
            await ac.post(
                "/v1/erp/mandates",
                json={
                    "titulaire": "Jean Mabiala",
                    "fonction": "gerant",
                    "date_nomination": "2023-01-15",
                    "duree_annees": 4,
                },
            )
        ).json()
        assert created["statut"] == "actif"
        assert created["fonction"] == "gerant"
        mandate_id = created["id"]

        listed = (await ac.get("/v1/erp/mandates")).json()["mandates"]
        assert any(m["id"] == mandate_id for m in listed)

        patched = (
            await ac.patch(f"/v1/erp/mandates/{mandate_id}", json={"statut": "expire"})
        ).json()
        assert patched["statut"] == "expire"

        deleted = await ac.delete(f"/v1/erp/mandates/{mandate_id}")
        assert deleted.status_code == 200

        after = await ac.patch(f"/v1/erp/mandates/{mandate_id}", json={"statut": "revoque"})
        assert after.status_code == 404


async def test_resolution_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        created = (
            await ac.post(
                "/v1/erp/resolutions",
                json={
                    "type_reunion": "AGO",
                    "date_reunion": "2026-06-30",
                    "objet": "Approbation des comptes de l'exercice 2025",
                    "decision": "Approuvés à l'unanimité",
                },
            )
        ).json()
        assert created["type_reunion"] == "AGO"
        resolution_id = created["id"]

        listed = (await ac.get("/v1/erp/resolutions")).json()["resolutions"]
        assert any(r["id"] == resolution_id for r in listed)

        patched = (
            await ac.patch(
                f"/v1/erp/resolutions/{resolution_id}",
                json={"reference_pv": "PV-2026-014"},
            )
        ).json()
        assert patched["reference_pv"] == "PV-2026-014"

        deleted = await ac.delete(f"/v1/erp/resolutions/{resolution_id}")
        assert deleted.status_code == 200
        remaining = await ac.delete(f"/v1/erp/resolutions/{resolution_id}")
        assert remaining.status_code == 404


async def test_corporate_echeances_mandat_alert(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # Nomination il y a ~335 jours, mandat de 1 an : échéance ~30 jours (< horizon 90j).
        date_nomination = date.today() - timedelta(days=335)
        await ac.post(
            "/v1/erp/mandates",
            json={
                "titulaire": "Alphonse Nkodia",
                "fonction": "administrateur",
                "date_nomination": date_nomination.isoformat(),
                "duree_annees": 1,
            },
        )

        result = (await ac.get("/v1/erp/corporate/echeances")).json()
        alertes = result["alertes"]
        assert any(a["categorie"] == "mandat" for a in alertes)


async def test_corporate_echeances_ago(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        date_cloture = date.today().replace(month=12, day=31)
        result = (
            await ac.get(f"/v1/erp/corporate/echeances?date_cloture={date_cloture.isoformat()}")
        ).json()
        alertes = result["alertes"]
        assert any(a["categorie"] == "ago" for a in alertes)
