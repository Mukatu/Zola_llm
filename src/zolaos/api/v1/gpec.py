"""SIRH — Référentiels (RME/RMC) + matrice de compétences + écarts GPEC.

Profil box. CRUD des référentiels + tableau croisé collaborateur × compétence
+ analyse d'écart GPEC (déterministe). Multi-tenant.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.rh_gpec import (
    EmployeeRef,
    EmpSkillRef,
    RoleSkillRef,
    SkillRef,
    gpec_gap,
    matrix,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    EmployeeRepository,
    EmployeeSkillRepository,
    JobRoleRepository,
    RoleSkillRepository,
    SkillRepository,
)

router = APIRouter(prefix="/v1/erp/hr", tags=["sirh"])


# ----------------------------------------------------------------- schémas


class JobRoleIn(BaseModel):
    code_emploi: str
    famille_professionnelle: str = ""
    intitule: str
    mission_principale: str = ""
    activites: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)


class SkillIn(BaseModel):
    code_competence: str
    domaine: str = "technique"
    intitule: str
    niveau_1: str = ""
    niveau_2: str = ""
    niveau_3: str = ""
    niveau_4: str = ""


class RoleSkillIn(BaseModel):
    code_emploi: str
    code_competence: str
    niveau_requis: int = Field(default=0, ge=0, le=4)


class EmployeeSkillIn(BaseModel):
    employee_matricule: str
    code_competence: str
    note: int = Field(default=0, ge=0, le=4)


# ----------------------------------------------------------------- RME / RMC / profil


@router.post("/job-roles", status_code=status.HTTP_201_CREATED, summary="Créer un emploi (RME)")
async def create_job_role(
    body: JobRoleIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await JobRoleRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/job-roles", summary="Lister les emplois (RME)")
async def list_job_roles(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await JobRoleRepository(session).list(tenant_id=tenant_id)
    return {"job_roles": [r.to_dict() for r in rows]}


@router.post("/skills", status_code=status.HTTP_201_CREATED, summary="Créer une compétence (RMC)")
async def create_skill(
    body: SkillIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await SkillRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/skills", summary="Lister les compétences (RMC)")
async def list_skills(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await SkillRepository(session).list(tenant_id=tenant_id)
    return {"skills": [r.to_dict() for r in rows]}


@router.post(
    "/role-skills", status_code=status.HTTP_201_CREATED, summary="Profil requis par emploi"
)
async def create_role_skill(
    body: RoleSkillIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await RoleSkillRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/role-skills", summary="Lister les profils requis")
async def list_role_skills(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await RoleSkillRepository(session).list(tenant_id=tenant_id)
    return {"role_skills": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- matrice


@router.post("/employee-skills", summary="Noter une compétence (matrice, upsert 0-4)")
async def set_employee_skill(
    body: EmployeeSkillIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await EmployeeSkillRepository(session).set_note(
        tenant_id=tenant_id,
        matricule=body.employee_matricule,
        code_competence=body.code_competence,
        note=body.note,
    )
    await session.commit()
    return rec.to_dict()


@router.get("/matrix", summary="Matrice de compétences (tableau croisé)")
async def competency_matrix(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    emps = [
        EmployeeRef(matricule=r.matricule, nom_complet=r.nom_complet, code_emploi=r.code_emploi)
        for r in await EmployeeRepository(session).list(tenant_id=tenant_id)
    ]
    skills = [
        SkillRef(code_competence=r.code_competence, domaine=r.domaine, intitule=r.intitule)
        for r in await SkillRepository(session).list(tenant_id=tenant_id)
    ]
    notes = [
        EmpSkillRef(matricule=r.employee_matricule, code_competence=r.code_competence, note=r.note)
        for r in await EmployeeSkillRepository(session).list(tenant_id=tenant_id)
    ]
    return dict(matrix(emps, skills, notes))


@router.get("/gpec", summary="Analyse d'écart GPEC (requis − détenu)")
async def gpec_analysis(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    emps = [
        EmployeeRef(matricule=r.matricule, nom_complet=r.nom_complet, code_emploi=r.code_emploi)
        for r in await EmployeeRepository(session).list(tenant_id=tenant_id)
    ]
    role_skills = [
        RoleSkillRef(
            code_emploi=r.code_emploi,
            code_competence=r.code_competence,
            niveau_requis=r.niveau_requis,
        )
        for r in await RoleSkillRepository(session).list(tenant_id=tenant_id)
    ]
    notes = [
        EmpSkillRef(matricule=r.employee_matricule, code_competence=r.code_competence, note=r.note)
        for r in await EmployeeSkillRepository(session).list(tenant_id=tenant_id)
    ]
    return dict(gpec_gap(emps, role_skills, notes))
