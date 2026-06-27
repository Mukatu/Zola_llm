"""Tests MKT-1 — marketing persisté : contacts/consentement, audience, envoi conforme."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/mkt.db")
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


async def test_contacts_audience_and_consent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 2 consentants newsletter, 1 non consentant
        await ac.post(
            "/v1/mkt/contacts",
            json={
                "id_externe": "C1",
                "nom": "Awa",
                "consentement_marketing": True,
                "finalites": ["newsletter"],
            },
        )
        await ac.post(
            "/v1/mkt/contacts",
            json={
                "id_externe": "C2",
                "nom": "Paul",
                "consentement_marketing": True,
                "finalites": ["newsletter", "promotions"],
            },
        )
        await ac.post(
            "/v1/mkt/contacts",
            json={
                "id_externe": "C3",
                "nom": "Sylvie",
                "consentement_marketing": False,
                "finalites": [],
            },
        )
        assert len((await ac.get("/v1/mkt/contacts")).json()["contacts"]) == 3

        aud = (await ac.get("/v1/mkt/audience-store?finalite=newsletter")).json()
        assert aud["consent"]["eligibles"] == 2
        assert aud["consent"]["exclus"] == 1


async def test_campaign_send_targets_only_consenting(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/mkt/contacts",
            json={
                "id_externe": "C1",
                "nom": "Awa",
                "consentement_marketing": True,
                "finalites": ["promotions"],
            },
        )
        await ac.post(
            "/v1/mkt/contacts",
            json={
                "id_externe": "C2",
                "nom": "Paul",
                "consentement_marketing": True,
                "finalites": ["newsletter"],
            },
        )
        camp = (
            await ac.post(
                "/v1/mkt/campaigns",
                json={"nom": "Soldes", "canal": "email", "finalite": "promotions"},
            )
        ).json()
        assert camp["statut"] == "brouillon"

        r = await ac.post(f"/v1/mkt/campaigns/{camp['id']}/send")
        body = r.json()
        # seul C1 (consent promotions) est ciblé ; C2 exclu
        assert body["campaign"]["nb_cibles"] == 1
        assert body["campaign"]["statut"] == "envoyee"
        assert body["exclus_non_consentants"] == 1

        # double envoi → 409
        assert (await ac.post(f"/v1/mkt/campaigns/{camp['id']}/send")).status_code == 409
