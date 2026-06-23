"""Tests SIRH Référentiels — matrice de compétences + écart GPEC (pur + SQLite)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.rh_gpec import (
    EmployeeRef,
    EmpSkillRef,
    RoleSkillRef,
    SkillRef,
    gpec_gap,
    matrix,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def test_matrix_cross_table() -> None:
    emps = [
        EmployeeRef(matricule="E1", nom_complet="A", code_emploi="DEV"),
        EmployeeRef(matricule="E2", nom_complet="B", code_emploi="DEV"),
    ]
    skills = [SkillRef(code_competence="C1"), SkillRef(code_competence="C2")]
    notes = [
        EmpSkillRef(matricule="E1", code_competence="C1", note=3),
        EmpSkillRef(matricule="E1", code_competence="C2", note=1),
        EmpSkillRef(matricule="E2", code_competence="C1", note=4),
    ]
    m = matrix(emps, skills, notes)
    assert m["competences"] == ["C1", "C2"]
    lignes = {ligne["matricule"]: ligne["notes"] for ligne in m["lignes"]}  # type: ignore[index,union-attr]
    assert lignes["E1"] == {"C1": 3, "C2": 1}
    assert lignes["E2"] == {"C1": 4, "C2": 0}  # défaut 0


def test_gpec_gap_and_critiques() -> None:
    emps = [
        EmployeeRef(matricule="E1", nom_complet="A", code_emploi="DEV"),
        EmployeeRef(matricule="E2", nom_complet="B", code_emploi="DEV"),
    ]
    role_skills = [
        RoleSkillRef(code_emploi="DEV", code_competence="C1", niveau_requis=4),
        RoleSkillRef(code_emploi="DEV", code_competence="C2", niveau_requis=2),
    ]
    notes = [
        EmpSkillRef(matricule="E1", code_competence="C1", note=3),
        EmpSkillRef(matricule="E2", code_competence="C1", note=4),
        EmpSkillRef(matricule="E2", code_competence="C2", note=2),
    ]
    g = gpec_gap(emps, role_skills, notes)
    par = {x["matricule"]: x for x in g["par_employe"]}  # type: ignore[union-attr]
    assert par["E1"]["couverture_pct"] == "0.0"  # ni C1(4) ni C2(2) atteints
    assert par["E2"]["couverture_pct"] == "100.0"
    assert g["experts_par_competence"] == {"C1": 1}  # E2 note 4
    crit = {c["code_competence"] for c in g["competences_critiques"]}  # type: ignore[union-attr]
    assert "C2" in crit  # aucune note 4 sur C2


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/gpec.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_referentiels_endpoints(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/employees",
            json={
                "matricule": "E1",
                "nom_complet": "Awa",
                "date_embauche": "2024-01-01",
                "code_emploi": "DEV",
            },
        )
        await ac.post(
            "/v1/erp/hr/job-roles", json={"code_emploi": "DEV", "intitule": "Développeur"}
        )
        await ac.post("/v1/erp/hr/skills", json={"code_competence": "C1", "intitule": "Python"})
        await ac.post(
            "/v1/erp/hr/role-skills",
            json={"code_emploi": "DEV", "code_competence": "C1", "niveau_requis": 4},
        )
        # upsert : deux notes successives, la dernière gagne
        await ac.post(
            "/v1/erp/hr/employee-skills",
            json={"employee_matricule": "E1", "code_competence": "C1", "note": 2},
        )
        await ac.post(
            "/v1/erp/hr/employee-skills",
            json={"employee_matricule": "E1", "code_competence": "C1", "note": 3},
        )

        m = (await ac.get("/v1/erp/hr/matrix")).json()
        assert m["competences"] == ["C1"]
        assert m["lignes"][0]["notes"]["C1"] == 3

        g = (await ac.get("/v1/erp/hr/gpec")).json()
        e1 = g["par_employe"][0]
        assert e1["ecarts"][0]["ecart"] == 1  # requis 4 - détenu 3
