"""PILOT-HIST — historisation des instantanés de pilotage (BI + portefeuille Fintech)."""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/hist.db")
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


async def test_bi_snapshot_et_historique(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # Deux captures → l'historique en compte deux, croissant par date.
        s1 = (await ac.post("/v1/bi/snapshot")).json()
        assert s1["domaine"] == "bi"
        assert "kpis" in s1["payload"]
        await ac.post("/v1/bi/snapshot")

        hist = (await ac.get("/v1/bi/snapshots")).json()["snapshots"]
        assert len(hist) == 2
        assert all("captured_at" in h and "kpis" in h for h in hist)
        assert hist[0]["captured_at"] <= hist[1]["captured_at"]


async def test_portfolio_snapshot_et_tendance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        snap = (await ac.post("/v1/fintech/portfolio/snapshot")).json()
        assert snap["domaine"] == "fintech_portfolio"
        # Le snapshot fige les stats complètes du portefeuille.
        assert "nb_dossiers" in snap["payload"]

        hist = (await ac.get("/v1/fintech/portfolio/history")).json()["history"]
        assert len(hist) == 1
        pt = hist[0]
        # L'historique n'expose que les métriques de tendance.
        for k in ("captured_at", "nb_dossiers", "par30_pct", "taux_acceptation_pct"):
            assert k in pt


async def test_bi_et_portfolio_isoles_par_domaine(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post("/v1/bi/snapshot")
        await ac.post("/v1/fintech/portfolio/snapshot")
        # Chaque historique ne voit que son domaine.
        assert len((await ac.get("/v1/bi/snapshots")).json()["snapshots"]) == 1
        assert len((await ac.get("/v1/fintech/portfolio/history")).json()["history"]) == 1
