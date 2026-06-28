"""Tests PAIE-3 — DAS 1 : agrégation annuelle (moteur) + endpoints état annuel/DAS1/export."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from io import BytesIO

import openpyxl
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.das1 import LignePaie, Salarie, construire_das1
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/das1.db")
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


def test_construire_das1_agrege() -> None:
    lignes = [
        LignePaie(
            matricule="E1", mois=1, brut_xaf="500000", base_imposable_xaf="400000", irpp_xaf="20000"
        ),
        LignePaie(
            matricule="E1", mois=2, brut_xaf="500000", base_imposable_xaf="400000", irpp_xaf="20000"
        ),
        LignePaie(
            matricule="E2", mois=1, brut_xaf="300000", base_imposable_xaf="240000", irpp_xaf="5000"
        ),
    ]
    salaries = [Salarie(matricule="E1", nom="AWA", sexe="F", profession="Cadre")]
    das1 = construire_das1(lignes, salaries, exercice="2026", plafond_mensuel_xaf=Decimal("450000"))
    assert das1.nb_salaries == 2
    assert das1.total_brut_xaf == Decimal("1300000")  # 1M + 300k
    e1 = next(x for x in das1.etat_annuel if x.matricule == "E1")
    assert e1.mensuels_xaf[0] == Decimal("500000") and e1.mensuels_xaf[1] == Decimal("500000")
    assert e1.total_xaf == Decimal("1000000")
    d1 = next(x for x in das1.lignes if x.matricule == "E1")
    assert d1.nom == "AWA"
    # plafonné : min(500k, 450k) × 2 mois = 900k
    assert d1.salaire_plafonne_xaf == Decimal("900000")
    assert d1.base_imposable_xaf == Decimal("800000")  # 2 × 400k


async def test_das1_endpoints_and_export(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        for mois in ("2026-01", "2026-02"):
            await ac.post(
                "/v1/erp/payslips",
                json={
                    "employee_matricule": "E1",
                    "periode": mois,
                    "brut_mensuel_xaf": "500000",
                    "allow_unvalidated": True,
                },
            )
        await ac.post(
            "/v1/erp/payslips",
            json={
                "employee_matricule": "E2",
                "periode": "2026-01",
                "brut_mensuel_xaf": "300000",
                "allow_unvalidated": True,
            },
        )

        etat = (await ac.get("/v1/erp/payroll/etat-annuel?annee=2026")).json()
        assert len(etat["mois"]) == 12
        e1 = next(x for x in etat["lignes"] if x["matricule"] == "E1")
        assert e1["total_xaf"] == "1000000"

        # identité DAS1 enrichie (PAIE-3c) via le registre du personnel
        await ac.post(
            "/v1/erp/employees",
            json={
                "matricule": "E1",
                "nom_complet": "AWA OKEMBA",
                "date_embauche": "2024-01-01",
                "situation_matrimoniale": "marie",
                "nationalite": "congolaise",
                "nb_enfants": 3,
                "livret_cnss": "LV-001",
            },
        )
        das1 = (await ac.get("/v1/erp/payroll/das1?annee=2026")).json()
        assert das1["nb_salaries"] == 2
        assert das1["totaux"]["brut_xaf"] == "1300000"
        assert "raison_sociale" in das1["employeur"]
        e1 = next(x for x in das1["lignes"] if x["matricule"] == "E1")
        assert e1["nom"] == "AWA OKEMBA"
        assert e1["situation_matrimoniale"] == "marie"
        assert e1["nb_enfants"] == 3
        assert e1["livret_cnss"] == "LV-001"

        r = await ac.get("/v1/erp/payroll/das1/export?annee=2026")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]
        wb = openpyxl.load_workbook(BytesIO(r.content))
        assert {"ETAT ANNUEL BRUT & IRPP", "DAS 1"} <= set(wb.sheetnames)
