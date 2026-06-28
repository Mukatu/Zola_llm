"""Tests PAIE-1 — bulletins historisés : émission, upsert, dashboard masse salariale."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/paie.db")
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


async def test_emission_upsert_and_dashboard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # barème CG non validé par défaut → simulation explicite (allow_unvalidated)
        r = await ac.post(
            "/v1/erp/payslips",
            json={
                "employee_matricule": "E1",
                "periode": "2026-06",
                "brut_mensuel_xaf": "500000",
                "allow_unvalidated": True,
            },
        )
        assert r.status_code == 201, r.text
        bulletin = r.json()
        assert bulletin["employee_matricule"] == "E1"
        assert Decimal(bulletin["net_a_payer_xaf"]) < Decimal("500000")  # net < brut
        assert Decimal(bulletin["cout_employeur_xaf"]) > Decimal("500000")  # coût > brut

        # ré-émission même (matricule, période) → upsert, pas de doublon
        await ac.post(
            "/v1/erp/payslips",
            json={
                "employee_matricule": "E1",
                "periode": "2026-06",
                "brut_mensuel_xaf": "600000",
                "allow_unvalidated": True,
            },
        )
        rows = (await ac.get("/v1/erp/payslips?periode=2026-06")).json()["payslips"]
        assert len(rows) == 1
        assert Decimal(rows[0]["brut_xaf"]) == Decimal("600000")

        # 2e salarié
        await ac.post(
            "/v1/erp/payslips",
            json={
                "employee_matricule": "E2",
                "periode": "2026-06",
                "brut_mensuel_xaf": "400000",
                "allow_unvalidated": True,
            },
        )
        dash = (await ac.get("/v1/erp/payroll/dashboard?periode=2026-06")).json()
        assert dash["nb_bulletins"] == 2
        assert Decimal(dash["masse_salariale_brute_xaf"]) == Decimal("1000000")  # 600k + 400k
        assert Decimal(dash["cout_employeur_total_xaf"]) > Decimal("1000000")
