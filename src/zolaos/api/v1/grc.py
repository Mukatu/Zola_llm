"""GRC — Gouvernance / Risque / Conformité : registre de conformité (GRC-1).

Profil box. Système de référence léger : obligations réglementaires/contractuelles
→ contrôles internes → constats (findings). Endpoint `/plan-controle` : synthèse
déterministe de pilotage (couverture, retards, échéances, taux de conformité).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.grc.conformite import (
    ControlLite,
    FindingLite,
    ObligationLite,
    synthese_conformite,
)
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    ControlRepository,
    FindingRepository,
    ObligationRepository,
)

router = APIRouter(prefix="/v1/grc", tags=["grc"])


# --------------------------------------------------------------------- schémas


class ObligationIn(BaseModel):
    reference: str = ""
    intitule: str
    domaine: str = "autre"
    autorite: str = ""
    periodicite: str = "ponctuelle"
    echeance: date | None = None
    base_legale: str = ""
    statut: str = "active"
    country: str = "cg"


class ObligationPatch(BaseModel):
    reference: str | None = None
    intitule: str | None = None
    domaine: str | None = None
    autorite: str | None = None
    periodicite: str | None = None
    echeance: date | None = None
    base_legale: str | None = None
    statut: str | None = None


class ControlIn(BaseModel):
    obligation_id: str | None = None
    intitule: str
    type_controle: str = "preventif"
    frequence: str = "ponctuel"
    responsable: str = ""
    derniere_execution: date | None = None
    prochaine_execution: date | None = None
    statut: str = "planifie"
    country: str = "cg"


class ControlPatch(BaseModel):
    obligation_id: str | None = None
    intitule: str | None = None
    type_controle: str | None = None
    frequence: str | None = None
    responsable: str | None = None
    derniere_execution: date | None = None
    prochaine_execution: date | None = None
    statut: str | None = None


class FindingIn(BaseModel):
    obligation_id: str | None = None
    control_id: str | None = None
    intitule: str
    gravite: str = "mineur"
    statut: str = "ouvert"
    date_constat: date
    echeance_correction: date | None = None
    plan_action: str = ""
    responsable: str = ""
    country: str = "cg"


class FindingPatch(BaseModel):
    intitule: str | None = None
    gravite: str | None = None
    statut: str | None = None
    echeance_correction: date | None = None
    plan_action: str | None = None
    responsable: str | None = None


# ------------------------------------------------------------------ obligations


@router.post("/obligations", status_code=status.HTTP_201_CREATED, summary="Créer une obligation")
async def create_obligation(
    body: ObligationIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await ObligationRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/obligations", summary="Lister les obligations")
async def list_obligations(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await ObligationRepository(session).list(tenant_id=tenant_id)
    return {"obligations": [r.to_dict() for r in rows]}


@router.patch("/obligations/{obligation_id}", summary="Mettre à jour une obligation")
async def patch_obligation(
    obligation_id: str,
    body: ObligationPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await ObligationRepository(session).update(
        obligation_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="obligation_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/obligations/{obligation_id}", summary="Supprimer une obligation")
async def delete_obligation(
    obligation_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    ok = await ObligationRepository(session).delete(obligation_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="obligation_not_found")
    await session.commit()
    return {"status": "deleted"}


# --------------------------------------------------------------------- contrôles


@router.post("/controls", status_code=status.HTTP_201_CREATED, summary="Créer un contrôle")
async def create_control(
    body: ControlIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await ControlRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/controls", summary="Lister les contrôles")
async def list_controls(
    tenant_id: str = "local",
    obligation_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await ControlRepository(session).list(tenant_id=tenant_id, obligation_id=obligation_id)
    return {"controls": [r.to_dict() for r in rows]}


@router.patch("/controls/{control_id}", summary="Mettre à jour un contrôle")
async def patch_control(
    control_id: str,
    body: ControlPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await ControlRepository(session).update(
        control_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/controls/{control_id}", summary="Supprimer un contrôle")
async def delete_control(
    control_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    ok = await ControlRepository(session).delete(control_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control_not_found")
    await session.commit()
    return {"status": "deleted"}


# ----------------------------------------------------------------------- constats


@router.post("/findings", status_code=status.HTTP_201_CREATED, summary="Créer un constat")
async def create_finding(
    body: FindingIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await FindingRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/findings", summary="Lister les constats")
async def list_findings(
    tenant_id: str = "local",
    obligation_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await FindingRepository(session).list(tenant_id=tenant_id, obligation_id=obligation_id)
    return {"findings": [r.to_dict() for r in rows]}


@router.patch("/findings/{finding_id}", summary="Mettre à jour un constat")
async def patch_finding(
    finding_id: str,
    body: FindingPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await FindingRepository(session).update(
        finding_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="finding_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/findings/{finding_id}", summary="Supprimer un constat")
async def delete_finding(
    finding_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    ok = await FindingRepository(session).delete(finding_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="finding_not_found")
    await session.commit()
    return {"status": "deleted"}


# ------------------------------------------------------------- plan de contrôle


@router.get("/plan-controle", summary="Synthèse de conformité (couverture, retards, échéances)")
async def plan_controle(
    tenant_id: str = "local",
    horizon_jours: int = 90,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    obligations = await ObligationRepository(session).list(tenant_id=tenant_id)
    controls = await ControlRepository(session).list(tenant_id=tenant_id)
    findings = await FindingRepository(session).list(tenant_id=tenant_id)

    synth = synthese_conformite(
        [ObligationLite(**o.to_dict()) for o in obligations],
        [ControlLite(**c.to_dict()) for c in controls],
        [FindingLite(**f.to_dict()) for f in findings],
        today=date.today(),
        horizon_jours=horizon_jours,
    )
    return synth.model_dump(mode="json")
