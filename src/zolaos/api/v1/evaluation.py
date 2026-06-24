"""SIRH-3b — Évaluations (9-box) + GPEC avancé (plan de formation, risques/opportunités).

Profil box. CRUD des évaluations + analytics déterministes sur le store
(référentiels, matrice, catalogue formation, employés). Multi-tenant.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.evaluation import EvaluationRef, talent_review
from zolaos.agents.erp.rh_gpec import (
    EmployeeRef,
    EmpSkillRef,
    RoleSkillRef,
    TrainingForGpec,
    plan_formation,
    risques_opportunites,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    EmployeeRepository,
    EmployeeSkillRepository,
    EvaluationRepository,
    RoleSkillRepository,
    TrainingRepository,
)

router = APIRouter(prefix="/v1/erp/hr", tags=["sirh"])


class EvaluationIn(BaseModel):
    employee_matricule: str
    periode: str = ""
    performance: int = Field(default=3, ge=1, le=5)
    potentiel: int = Field(default=3, ge=1, le=5)
    objectifs: str = ""
    commentaire: str = ""
    statut: str = "brouillon"


# ----------------------------------------------------------------- évaluations


@router.post("/evaluations", status_code=status.HTTP_201_CREATED, summary="Créer une évaluation")
async def create_evaluation(
    body: EvaluationIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await EvaluationRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/evaluations", summary="Lister les évaluations")
async def list_evaluations(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await EvaluationRepository(session).list(tenant_id=tenant_id)
    return {"evaluations": [r.to_dict() for r in rows]}


@router.delete("/evaluations/{ev_id}", summary="Supprimer une évaluation")
async def delete_evaluation(
    ev_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await EvaluationRepository(session).delete(ev_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluation_not_found")
    await session.commit()
    return {"deleted": ev_id}


# ----------------------------------------------------------------- analytics


async def _eval_refs(tenant_id: str, session: AsyncSession) -> list[EvaluationRef]:
    return [
        EvaluationRef(
            matricule=r.employee_matricule,
            periode=r.periode,
            performance=r.performance,
            potentiel=r.potentiel,
        )
        for r in await EvaluationRepository(session).list(tenant_id=tenant_id)
    ]


@router.get("/talent-review", summary="Revue de talents (matrice 9-box)")
async def talent_review_endpoint(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    return dict(talent_review(await _eval_refs(tenant_id, session)))


async def _gpec_inputs(tenant_id: str, session: AsyncSession):  # type: ignore[no-untyped-def]
    employees = [
        EmployeeRef(
            matricule=r.matricule,
            nom_complet=r.nom_complet,
            code_emploi=r.code_emploi,
            date_naissance=r.date_naissance,
        )
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
    return employees, role_skills, notes


@router.get("/gpec/plan-formation", summary="Plan de formation suggéré (écarts × catalogue)")
async def gpec_plan_formation(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    employees, role_skills, notes = await _gpec_inputs(tenant_id, session)
    trainings = [
        TrainingForGpec(code=r.code, intitule=r.intitule, competences_visees=r.competences_visees)
        for r in await TrainingRepository(session).list(tenant_id=tenant_id)
    ]
    return {"suggestions": plan_formation(employees, role_skills, notes, trainings)}


@router.get("/gpec/risks", summary="Matrice risques & opportunités RH")
async def gpec_risks(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    employees, role_skills, notes = await _gpec_inputs(tenant_id, session)
    review = talent_review(await _eval_refs(tenant_id, session))
    hp = review["hauts_potentiels"]
    hauts = hp if isinstance(hp, list) else []
    return dict(risques_opportunites(employees, role_skills, notes, hauts_potentiels=hauts))
