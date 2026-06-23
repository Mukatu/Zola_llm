"""Tests SIRH-1 — indicateurs RH (pur) + CRUD/dashboard/échéancier (SQLite)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.rh_pilotage import (
    AbsenceHR,
    ContractHR,
    EmployeeHR,
    dashboard,
    echeancier,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase

TODAY = date(2026, 6, 23)


def _emp(mat: str, genre: str, salaire: str, embauche: date, **kw) -> EmployeeHR:  # type: ignore[no-untyped-def]
    return EmployeeHR(
        matricule=mat,
        nom_complet=f"E {mat}",
        genre=genre,
        date_embauche=embauche,
        salaire_base_xaf=Decimal(salaire),
        **kw,
    )


def test_dashboard_indicateurs() -> None:
    emps = [
        _emp("E1", "H", "600000", date(2022, 1, 1), departement="IT", manager_matricule=None),
        _emp("E2", "F", "400000", date(2024, 6, 1), departement="IT", manager_matricule="E1"),
        _emp("E3", "H", "500000", date(2025, 1, 1), departement="RH", manager_matricule="E1"),
        _emp("E4", "F", "300000", date(2023, 1, 1), statut="sorti", date_sortie=date(2026, 3, 1)),
    ]
    cons = [ContractHR(employee_matricule="E1", type="CDI", date_debut=date(2022, 1, 1))]
    abs_ = [
        AbsenceHR(
            employee_matricule="E2",
            type="maladie",
            date_debut=date(2026, 1, 5),
            date_fin=date(2026, 1, 9),
            jours=Decimal("5"),
        )
    ]
    d = dashboard(emps, cons, abs_, today=TODAY)
    assert d.effectif == 3  # E4 sorti exclu
    assert d.masse_salariale_xaf == "1500000"
    assert d.repartition_genre == {"H": 2, "F": 1}
    assert d.par_departement == {"IT": 2, "RH": 1}
    # 1 sortie (E4) sur effectif 3 → turnover 33.33 %
    assert d.turnover_pct == "33.33"
    # encadrant unique E1 → 1/3 = 33.33 %
    assert d.ratio_encadrement_pct == "33.33"


def test_echeancier_fin_cdd() -> None:
    emps = [_emp("E1", "H", "400000", date(2026, 1, 1))]
    cons = [
        ContractHR(
            employee_matricule="E1",
            type="CDD",
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 7, 15),
        )
    ]
    ech = echeancier(emps, cons, today=TODAY, horizon_jours=60)
    types = {e.categorie for e in ech}
    assert "fin_cdd" in types


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/sirh.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_sirh_crud_and_dashboard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/employees",
            json={
                "matricule": "E1",
                "nom_complet": "Awa",
                "genre": "F",
                "date_embauche": "2024-01-01",
                "departement": "Finance",
                "salaire_base_xaf": "500000",
            },
        )
        assert r.status_code == 201, r.text

        r = await ac.get("/v1/erp/employees")
        assert len(r.json()["employees"]) == 1

        r = await ac.get("/v1/erp/hr/dashboard")
        d = r.json()
        assert d["effectif"] == 1
        assert d["masse_salariale_xaf"] == "500000.00"  # Numeric(18,2) persisté

        r = await ac.get("/v1/erp/hr/registre")
        assert r.json()["registre"][0]["matricule"] == "E1"
