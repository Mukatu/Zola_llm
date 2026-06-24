"""Tests SIRH-3a Formation — indicateurs (pur) + CRUD/dashboard (SQLite)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.formation import (
    EnrollmentRef,
    SessionRef,
    TrainingEvalRef,
    TrainingRef,
    formation_dashboard,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def test_formation_dashboard() -> None:
    trainings = [
        TrainingRef(
            code="T1",
            intitule="SYSCOHADA",
            competences_visees=["C1"],
            duree_heures=Decimal("14"),
            cout_xaf=Decimal("100000"),
        ),
    ]
    sessions = [SessionRef(id="S1", training_code="T1", date_debut=date(2026, 5, 1))]
    enrollments = [
        EnrollmentRef(id="E1", session_id="S1", employee_matricule="M1", statut="realise"),
        EnrollmentRef(id="E2", session_id="S1", employee_matricule="M2", statut="inscrit"),
    ]
    evals = [
        TrainingEvalRef(enrollment_id="E1", type="chaud", satisfaction=4),
        TrainingEvalRef(enrollment_id="E1", type="froid", acquis=3),
    ]
    d = formation_dashboard(trainings, sessions, enrollments, evals)
    assert d.nb_inscriptions == 2
    assert d.nb_realisees == 1
    assert d.taux_realisation_pct == "50.0"
    assert d.cout_total_xaf == "100000"  # 1 réalisé
    assert d.satisfaction_moyenne == "4.0"
    assert d.efficacite_moyenne == "3.0"
    assert d.competences_visees == ["C1"]


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/form.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_formation_crud_and_dashboard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/formation/trainings",
            json={
                "code": "T1",
                "intitule": "SYSCOHADA",
                "competences_visees": ["C1"],
                "duree_heures": "14",
                "cout_xaf": "100000",
            },
        )
        s = (
            await ac.post(
                "/v1/erp/formation/sessions",
                json={"training_code": "T1", "date_debut": "2026-05-01"},
            )
        ).json()
        e = (
            await ac.post(
                "/v1/erp/formation/enrollments",
                json={"session_id": s["id"], "employee_matricule": "M1"},
            )
        ).json()
        # marquer réalisé
        r = await ac.patch(f"/v1/erp/formation/enrollments/{e['id']}", json={"statut": "realise"})
        assert r.status_code == 200

        d = (await ac.get("/v1/erp/formation/dashboard")).json()
        assert d["nb_realisees"] == 1
        assert d["cout_total_xaf"] == "100000.00"  # Numeric(18,2) persisté
