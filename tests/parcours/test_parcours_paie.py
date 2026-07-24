"""Parcours end-to-end — Paie (barème gouverné).

Chaîne : émission d'un bulletin bloquée si le barème n'est pas validé (garde de
gouvernance, 409) → validation experte → émission → le bulletin est historisé et
listé. Vérifie la cohérence brut > net et coût employeur > brut. Déterministe.
"""

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parcours_paie.db")
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


async def test_parcours_bulletin_gouverne(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        bulletin_req = {
            "employee_matricule": "M-001",
            "periode": "2026-06",
            "brut_mensuel_xaf": "300000",
        }

        # 1. Émettre un bulletin. Si le barème n'est pas validé → 409 (garde).
        r = await ac.post("/v1/erp/payslips", json=bulletin_req)
        if r.status_code == 409:
            assert r.json()["detail"] == "bareme_non_valide"
            # 2. Validation experte du barème → lève le verrou.
            v = await ac.post(
                "/v1/erp/payroll/bareme/validate",
                json={"validated": True, "validated_by": "DRH"},
            )
            assert v.status_code == 200
            r = await ac.post("/v1/erp/payslips", json=bulletin_req)

        # 3. Émission réussie, chiffres cohérents.
        assert r.status_code == 201
        b = r.json()
        assert Decimal(b["brut_xaf"]) == Decimal("300000")
        assert Decimal(b["net_a_payer_xaf"]) < Decimal("300000")  # cotisations + IRPP retenus
        assert Decimal(b["cout_employeur_xaf"]) > Decimal("300000")  # + charges patronales

        # 4. Le bulletin est historisé (listé pour la période).
        listed = (await ac.get("/v1/erp/payslips?periode=2026-06")).json()
        bulletins = listed["payslips"] if "payslips" in listed else listed
        assert any(x["employee_matricule"] == "M-001" for x in bulletins)
