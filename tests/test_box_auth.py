"""Le plan de données de la box exige une authentification (`require_box_auth`).

On retire le bypass de test (posé par conftest) pour vérifier le vrai
comportement : sans identité, les endpoints métier répondent 401.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.api.auth import require_box_auth
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/boxauth.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    # Retirer le bypass d'auth de test → comportement réel (401 attendu).
    app.dependency_overrides.pop(require_box_auth, None)
    app.dependency_overrides[get_session] = _override
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


async def test_plan_de_donnees_exige_auth(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        protegees = (
            "/v1/erp/invoices",
            "/v1/bi/cockpit",
            "/v1/fintech/aml-cases",
            "/v1/cyber/audits",
            "/v1/grc/obligations",
        )
        for path in protegees:
            r = await ac.get(path)
            assert r.status_code == 401, f"{path} doit exiger une authentification"


async def test_avec_bypass_de_test_ca_passe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Contrôle : avec le bypass conftest (non retiré), les mêmes endpoints répondent."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/boxauth2.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())  # bypass conftest actif
    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/v1/bi/cockpit")).status_code == 200
    await engine.dispose()
