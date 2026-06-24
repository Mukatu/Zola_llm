"""Tests SIRH-3b — 9-box + GPEC avancé (pur) + endpoints (SQLite)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.evaluation import EvaluationRef, talent_review
from zolaos.agents.erp.rh_gpec import (
    EmployeeRef,
    EmpSkillRef,
    RoleSkillRef,
    TrainingForGpec,
    plan_formation,
    risques_opportunites,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def test_9box() -> None:
    evals = [
        EvaluationRef(matricule="M1", performance=5, potentiel=5),
        EvaluationRef(matricule="M2", performance=1, potentiel=3),
    ]
    r = talent_review(evals)
    assert r["top_talents"] == ["M1"]  # type: ignore[index]
    assert r["sous_performeurs"] == ["M2"]  # type: ignore[index]
    assert r["grid"]["haut/haut"] == ["M1"]  # type: ignore[index]


def test_plan_formation_et_risques() -> None:
    emps = [EmployeeRef(matricule="M1", nom_complet="A", code_emploi="DEV")]
    role_skills = [RoleSkillRef(code_emploi="DEV", code_competence="C1", niveau_requis=4)]
    notes = [EmpSkillRef(matricule="M1", code_competence="C1", note=2)]
    trainings = [TrainingForGpec(code="T1", competences_visees=["C1"])]
    plan = plan_formation(emps, role_skills, notes, trainings)
    assert plan[0]["ecart"] == 2
    assert plan[0]["formations"] == ["T1"]

    ro = risques_opportunites(emps, role_skills, notes, hauts_potentiels=["M1"])
    types = {r["type"] for r in ro["risques"]}  # type: ignore[union-attr]
    assert "competence_critique" in types  # C1 requise, 0 expert
    assert any(o["type"] == "haut_potentiel" for o in ro["opportunites"])  # type: ignore[union-attr]


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/eval.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_evaluations_and_talent_review(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/hr/evaluations",
            json={"employee_matricule": "M1", "periode": "2026", "performance": 5, "potentiel": 5},
        )
        r = await ac.get("/v1/erp/hr/talent-review")
        assert r.json()["top_talents"] == ["M1"]
