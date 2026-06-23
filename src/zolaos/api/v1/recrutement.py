"""SIRH — Recrutement : registres (vacances, candidats, candidatures, entretiens)
+ pipeline + indicateurs déterministes. Profil box, multi-tenant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.recrutement import (
    ApplicationRef,
    CandidateRef,
    VacancyRef,
    recruitment_dashboard,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    ApplicationRepository,
    CandidateRepository,
    InterviewRepository,
    VacancyRepository,
)

router = APIRouter(prefix="/v1/erp/recruitment", tags=["sirh"])


class VacancyIn(BaseModel):
    code_vacance: str
    code_emploi: str | None = None
    intitule: str
    motif: str = "creation"
    type_contrat_cible: str = "CDI"
    nb_postes: int = 1
    departement: str = ""
    lieu: str = ""
    statut: str = "ouverte"
    priorite: str = "moyenne"
    date_ouverture: date
    date_cible: date | None = None
    manager_demandeur: str | None = None
    budget_xaf: Decimal | None = None
    country: str = "cg"


class CandidateIn(BaseModel):
    nom: str
    prenom: str = ""
    email: str | None = None
    telephone: str | None = None
    source: str = "spontanee"
    cv_uri: str | None = None
    statut_vivier: str = "actif"


class ApplicationIn(BaseModel):
    candidate_id: str
    code_vacance: str
    etape: str = "reçue"
    date_candidature: date
    note_globale: int | None = None
    decision: str | None = None


class ApplicationMove(BaseModel):
    etape: str
    note_globale: int | None = None
    decision: str | None = None


class InterviewIn(BaseModel):
    application_id: str
    date_prevue: date | None = None
    type: str = "RH"
    grille: list[Any] = Field(default_factory=list)
    score_global: int | None = None
    recommandation: str | None = None
    statut: str = "planifie"


# ----------------------------------------------------------------- vacances


@router.post("/vacancies", status_code=status.HTTP_201_CREATED, summary="Créer une vacance")
async def create_vacancy(
    body: VacancyIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await VacancyRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/vacancies", summary="Lister les vacances")
async def list_vacancies(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await VacancyRepository(session).list(tenant_id=tenant_id)
    return {"vacancies": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- candidats


@router.post("/candidates", status_code=status.HTTP_201_CREATED, summary="Créer un candidat")
async def create_candidate(
    body: CandidateIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CandidateRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/candidates", summary="Lister les candidats")
async def list_candidates(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await CandidateRepository(session).list(tenant_id=tenant_id)
    return {"candidates": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- candidatures (pipeline)


@router.post("/applications", status_code=status.HTTP_201_CREATED, summary="Créer une candidature")
async def create_application(
    body: ApplicationIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await ApplicationRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/applications", summary="Lister les candidatures")
async def list_applications(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await ApplicationRepository(session).list(tenant_id=tenant_id)
    return {"applications": [r.to_dict() for r in rows]}


@router.patch("/applications/{app_id}", summary="Déplacer la candidature (pipeline)")
async def move_application(
    app_id: str,
    body: ApplicationMove,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    fields = {**body.model_dump(exclude_none=True), "date_etape": date.today()}
    rec = await ApplicationRepository(session).update(app_id, tenant_id=tenant_id, fields=fields)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await session.commit()
    return rec.to_dict()


# ----------------------------------------------------------------- entretiens


@router.post("/interviews", status_code=status.HTTP_201_CREATED, summary="Planifier un entretien")
async def create_interview(
    body: InterviewIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await InterviewRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/interviews", summary="Lister les entretiens")
async def list_interviews(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await InterviewRepository(session).list(tenant_id=tenant_id)
    return {"interviews": [r.to_dict() for r in rows]}


# ----------------------------------------------------------------- pilotage


@router.get("/dashboard", summary="Indicateurs de recrutement (entonnoir, time-to-hire)")
async def recruitment_kpis(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    vacancies = [
        VacancyRef(
            code_vacance=r.code_vacance,
            code_emploi=r.code_emploi,
            statut=r.statut,
            date_ouverture=r.date_ouverture,
            date_cible=r.date_cible,
            budget_xaf=r.budget_xaf,
        )
        for r in await VacancyRepository(session).list(tenant_id=tenant_id)
    ]
    candidates = [
        CandidateRef(id=r.id, source=r.source)
        for r in await CandidateRepository(session).list(tenant_id=tenant_id)
    ]
    applications = [
        ApplicationRef(
            candidate_id=r.candidate_id,
            code_vacance=r.code_vacance,
            etape=r.etape,
            date_candidature=r.date_candidature,
            date_etape=r.date_etape,
        )
        for r in await ApplicationRepository(session).list(tenant_id=tenant_id)
    ]
    return dict(recruitment_dashboard(vacancies, candidates, applications))
