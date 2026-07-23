"""Tests store Documents (transverse) — CRUD des artefacts persistés + filtre par type."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/documents.db")
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


async def test_document_crud(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        created = (
            await ac.post(
                "/v1/erp/documents",
                json={
                    "type": "contrat",
                    "metier": "droit",
                    "titre": "Contrat de bail commercial",
                    "contenu": "Article 1 — Objet…",
                    "tags": ["ohada", "bail"],
                },
            )
        ).json()
        assert created["titre"] == "Contrat de bail commercial"
        doc_id = created["id"]

        listed = (await ac.get("/v1/erp/documents")).json()["documents"]
        assert any(d["id"] == doc_id for d in listed)

        # Suppression, puis 404 sur seconde suppression.
        assert (await ac.delete(f"/v1/erp/documents/{doc_id}")).status_code == 200
        assert (await ac.delete(f"/v1/erp/documents/{doc_id}")).status_code == 404


async def test_document_filter_by_type(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post("/v1/erp/documents", json={"type": "contrat", "titre": "Bail"})
        await ac.post("/v1/erp/documents", json={"type": "rapport", "titre": "Audit RH"})

        contrats = (await ac.get("/v1/erp/documents?type=contrat")).json()["documents"]
        assert len(contrats) == 1
        assert contrats[0]["type"] == "contrat"
