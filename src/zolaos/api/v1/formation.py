"""SIRH-3a — Formation : catalogue, sessions, inscriptions, évaluations + pilotage.

Profil box. CRUD des registres + indicateurs déterministes (`formation`) sur le
store. Multi-tenant.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.formation import (
    EnrollmentRef,
    SessionRef,
    TrainingEvalRef,
    TrainingRef,
    formation_dashboard,
    formation_echeancier,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    TrainingEnrollmentRepository,
    TrainingEvaluationRepository,
    TrainingRepository,
    TrainingSessionRepository,
)

router = APIRouter(prefix="/v1/erp/formation", tags=["sirh"])


class TrainingIn(BaseModel):
    code: str
    intitule: str = ""
    competences_visees: list[str] = Field(default_factory=list)
    modalite: str = "presentiel"
    duree_heures: Decimal = Decimal("0")
    cout_xaf: Decimal = Decimal("0")


class SessionIn(BaseModel):
    training_code: str
    date_debut: date
    date_fin: date | None = None
    lieu: str = ""
    formateur: str = ""
    places: int = 0
    statut: str = "planifiee"


class EnrollmentIn(BaseModel):
    session_id: str
    employee_matricule: str
    statut: str = "inscrit"


class EnrollmentPatch(BaseModel):
    statut: str


class EvaluationIn(BaseModel):
    enrollment_id: str
    type: str = "chaud"
    satisfaction: int | None = None
    acquis: int | None = None
    date_eval: date | None = None


# ----------------------------------------------------------------- catalogue / sessions


@router.post("/trainings", status_code=status.HTTP_201_CREATED, summary="Créer une formation")
async def create_training(
    body: TrainingIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await TrainingRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/trainings", summary="Lister le catalogue")
async def list_trainings(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await TrainingRepository(session).list(tenant_id=tenant_id)
    return {"trainings": [r.to_dict() for r in rows]}


@router.post("/sessions", status_code=status.HTTP_201_CREATED, summary="Planifier une session")
async def create_session_(
    body: SessionIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await TrainingSessionRepository(session).create(
        {**body.model_dump(), "tenant_id": tenant_id}
    )
    await session.commit()
    return rec.to_dict()


@router.get("/sessions", summary="Lister les sessions")
async def list_sessions(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await TrainingSessionRepository(session).list(tenant_id=tenant_id)
    return {"sessions": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- inscriptions / évals


@router.post("/enrollments", status_code=status.HTTP_201_CREATED, summary="Inscrire un employé")
async def create_enrollment(
    body: EnrollmentIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await TrainingEnrollmentRepository(session).create(
        {**body.model_dump(), "tenant_id": tenant_id}
    )
    await session.commit()
    return rec.to_dict()


@router.get("/enrollments", summary="Lister les inscriptions")
async def list_enrollments(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await TrainingEnrollmentRepository(session).list(tenant_id=tenant_id)
    return {"enrollments": [r.to_dict() for r in rows]}


@router.patch("/enrollments/{enr_id}", summary="Mettre à jour le statut d'inscription")
async def patch_enrollment(
    enr_id: str,
    body: EnrollmentPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await TrainingEnrollmentRepository(session).update(
        enr_id, tenant_id=tenant_id, fields=body.model_dump()
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="enrollment_not_found")
    await session.commit()
    return rec.to_dict()


@router.post(
    "/evaluations", status_code=status.HTTP_201_CREATED, summary="Évaluation (chaud/froid)"
)
async def create_evaluation(
    body: EvaluationIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await TrainingEvaluationRepository(session).create(
        {**body.model_dump(), "tenant_id": tenant_id}
    )
    await session.commit()
    return rec.to_dict()


# ----------------------------------------------------------------- pilotage


async def _refs(tenant_id: str, session: AsyncSession):  # type: ignore[no-untyped-def]
    trainings = [
        TrainingRef(
            code=r.code,
            intitule=r.intitule,
            competences_visees=r.competences_visees,
            duree_heures=r.duree_heures,
            cout_xaf=r.cout_xaf,
        )
        for r in await TrainingRepository(session).list(tenant_id=tenant_id)
    ]
    sessions = [
        SessionRef(
            id=r.id,
            training_code=r.training_code,
            date_debut=r.date_debut,
            date_fin=r.date_fin,
            statut=r.statut,
        )
        for r in await TrainingSessionRepository(session).list(tenant_id=tenant_id)
    ]
    enrollments = [
        EnrollmentRef(
            id=r.id,
            session_id=r.session_id,
            employee_matricule=r.employee_matricule,
            statut=r.statut,
        )
        for r in await TrainingEnrollmentRepository(session).list(tenant_id=tenant_id)
    ]
    evaluations = [
        TrainingEvalRef(
            enrollment_id=r.enrollment_id, type=r.type, satisfaction=r.satisfaction, acquis=r.acquis
        )
        for r in await TrainingEvaluationRepository(session).list(tenant_id=tenant_id)
    ]
    return trainings, sessions, enrollments, evaluations


@router.get("/dashboard", summary="Tableau de bord formation (déterministe)")
async def formation_kpis(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    trainings, sessions, enrollments, evaluations = await _refs(tenant_id, session)
    return asdict(formation_dashboard(trainings, sessions, enrollments, evaluations))


@router.get("/echeancier", summary="Échéancier formation (sessions + évals à froid)")
async def formation_echeances(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    _, sessions, enrollments, evaluations = await _refs(tenant_id, session)
    return {
        "echeances": [asdict(e) for e in formation_echeancier(sessions, enrollments, evaluations)]
    }
