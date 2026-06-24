"""SIRH-2b — Documents (artefacts persistés) + génération.

Profil box. `store_documents` (transverse) + composition de prompts (fiche de
poste, grille, annonce, plan) depuis les référentiels + **contrats en masse**
(fusion déterministe). La rédaction libre est faite par l'agent RH côté client
(`/v1/query`) ; ici on prépare et on persiste. Multi-tenant.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.rh_generation import (
    DEFAULT_CONTRAT_TEMPLATE,
    compose_prompt,
    merge_template,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    DocumentRepository,
    EmployeeRepository,
    JobRoleRepository,
    RoleSkillRepository,
    SkillRepository,
    VacancyRepository,
)

router = APIRouter(prefix="/v1/erp", tags=["sirh"])

_TITRES = {
    "fiche_poste": "Fiche de poste",
    "grille_entretien": "Grille d'entretien",
    "annonce": "Annonce de recrutement",
    "plan_recrutement": "Plan de recrutement",
}


# ----------------------------------------------------------------- documents (CRUD)


class DocumentIn(BaseModel):
    type: str = "autre"
    metier: str = "rh"
    titre: str
    contenu: str = ""
    tags: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    statut: str = "brouillon"


@router.post("/documents", status_code=status.HTTP_201_CREATED, summary="Enregistrer un document")
async def create_document(
    body: DocumentIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await DocumentRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/documents", summary="Lister les documents")
async def list_documents(
    tenant_id: str = "local",
    type: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await DocumentRepository(session).list(tenant_id=tenant_id)
    docs = [r.to_dict() for r in rows if type is None or r.type == type]
    return {"documents": docs}


@router.delete("/documents/{doc_id}", summary="Supprimer un document")
async def delete_document(
    doc_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ok = await DocumentRepository(session).delete(doc_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    await session.commit()
    return {"deleted": doc_id}


# ----------------------------------------------------------------- génération


class GenerateIn(BaseModel):
    type: str  # fiche_poste | grille_entretien | annonce | plan_recrutement
    code_emploi: str | None = None
    code_vacance: str | None = None


@router.post("/hr/generate", summary="Composer un prompt RH (depuis RME/RMC) — déterministe")
async def hr_generate_prompt(
    body: GenerateIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    roles = await JobRoleRepository(session).list(tenant_id=tenant_id)
    role = next((r for r in roles if r.code_emploi == body.code_emploi), None)
    skills = {
        s.code_competence: s for s in await SkillRepository(session).list(tenant_id=tenant_id)
    }
    rskills = [
        rs
        for rs in await RoleSkillRepository(session).list(tenant_id=tenant_id)
        if rs.code_emploi == body.code_emploi
    ]
    competences = [
        {
            "code_competence": rs.code_competence,
            "intitule": (
                skills[rs.code_competence].intitule
                if rs.code_competence in skills
                else rs.code_competence
            ),
            "niveau_requis": rs.niveau_requis,
        }
        for rs in rskills
    ]
    vacs = await VacancyRepository(session).list(tenant_id=tenant_id)
    vac = next((v for v in vacs if v.code_vacance == body.code_vacance), None)

    intitule = (
        (role.intitule if role else None)
        or (vac.intitule if vac else None)
        or (body.code_emploi or "(emploi)")
    )
    context: dict[str, Any] = {
        "intitule": intitule,
        "mission": role.mission_principale if role else "",
        "activites": role.activites if role else [],
        "kpis": role.kpis if role else [],
        "competences": competences,
        "type_contrat": vac.type_contrat_cible if vac else "CDI",
        "lieu": vac.lieu if vac else "",
    }
    prompt = compose_prompt(body.type, context=context)
    titre = f"{_TITRES.get(body.type, body.type)} — {intitule}"
    return {"type": body.type, "titre": titre, "prompt": prompt}


class ContractsGenerateIn(BaseModel):
    matricules: list[str]
    type_contrat: str = "CDI"
    template: str | None = None
    employeur: str = "ZolaOS"
    lieu: str = "Brazzaville"
    date_debut: str = ""


@router.post(
    "/hr/contracts/generate", summary="Générer des contrats en masse (fusion déterministe)"
)
async def hr_generate_contracts(
    body: ContractsGenerateIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    emps = {e.matricule: e for e in await EmployeeRepository(session).list(tenant_id=tenant_id)}
    rows: list[dict[str, str]] = []
    for mat in body.matricules:
        e = emps.get(mat)
        if e is None:
            continue
        rows.append(
            {
                "matricule": mat,
                "nom_complet": e.nom_complet,
                "poste": e.poste,
                "salaire_xaf": str(e.salaire_base_xaf),
                "type_contrat": body.type_contrat,
                "employeur": body.employeur,
                "lieu": body.lieu,
                "date_debut": body.date_debut,
                "date_edition": date.today().isoformat(),
            }
        )
    contrats = merge_template(body.template or DEFAULT_CONTRAT_TEMPLATE, rows)
    return {
        "contrats": [
            {"matricule": r["matricule"], "contenu": c} for r, c in zip(rows, contrats, strict=True)
        ]
    }
