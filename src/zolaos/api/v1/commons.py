"""Communs de connaissance (niveau 3) — consentement + extraction (Phase A).

Endpoints authentifiés, tenant dérivé de l'identité. Le client ouvre (ou ferme)
la contribution par périmètre ; l'extraction dépose des candidats **anonymisés**
en quarantaine. Aucune promotion vers le moteur (Phases B/C). Cf.
docs/COMMONS_PIPELINE.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate, require_curator
from zolaos.commons import curation, learned
from zolaos.commons.pipeline import (
    capture_categorisation,
    get_optin,
    run_extraction,
    set_optin,
)
from zolaos.db.session import get_session

router = APIRouter(prefix="/v1/commons", tags=["commons"])


class OptinIn(BaseModel):
    enabled: bool = False
    scopes: list[str] = Field(default_factory=list)  # poles/modules autorisés


@router.get("/optin", summary="Consentement de contribution du locataire")
async def read_optin(
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tenant = principal.tenant_id or "local"
    row = await get_optin(session, tenant)
    if row is None:
        return {"tenant_id": tenant, "enabled": False, "scopes": [], "updated_by": None}
    return row.to_dict()


@router.put("/optin", summary="Activer / mettre à jour le consentement (par périmètre)")
async def update_optin(
    body: OptinIn,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tenant = principal.tenant_id or "local"
    row = await set_optin(
        session, tenant, enabled=body.enabled, scopes=body.scopes, updated_by=principal.email
    )
    await session.commit()
    return row.to_dict()


@router.post("/extract", summary="Extraire les candidats vers la quarantaine (aucune promotion)")
async def extract(
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tenant = principal.tenant_id or "local"
    res = await run_extraction(session, tenant)
    await session.commit()
    return res


# --------------------------------------------------------------------------
# Apprentissage déterministe générique (learned_rules) — tout métier
# --------------------------------------------------------------------------


class CorrectionIn(BaseModel):
    domaine: str = Field(..., min_length=1)  # ex : erp.compta, achats.objet, rh.classification
    libelle: str = Field(..., min_length=1)
    valeur: str = Field(..., min_length=1)


@router.post("/correction", summary="Capturer une correction (mapping) — tout métier")
async def correction(
    body: CorrectionIn,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Capture générique `(libellé → valeur)` pour un `domaine` — gaté par l'opt-in."""
    tenant = principal.tenant_id or "local"
    res = await capture_categorisation(
        session, tenant, libelle=body.libelle, valeur=body.valeur, domaine=body.domaine
    )
    await session.commit()
    return res


@router.get("/learned", summary="Règles apprises applicables à un libellé (tout métier)")
async def learned_rules(
    domaine: str,
    texte: str,
    _principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await learned.lookup(session, domaine, texte)
    return {"regles": [r.to_dict() for r in rows]}


# --------------------------------------------------------------------------
# Curation (Phase B) — réservée au scope commons:curate
# --------------------------------------------------------------------------


@router.get("/candidates", summary="Candidats à curer (pré-filtrés par k-anonymat)")
async def list_candidates(
    status_filter: str | None = "pending",
    eligible_only: bool = True,
    _curator: Principal = Depends(require_curator),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await curation.list_candidates(
        session, status=status_filter, eligible_only=eligible_only
    )
    return {
        "k_anonymat": curation.K_ANONYMITY,
        "total": len(rows),
        "candidats": [c.to_dict() for c in rows],
    }


@router.post("/candidates/{candidate_id}/validate", summary="Valider un candidat (humain)")
async def validate_candidate(
    candidate_id: str,
    curator: Principal = Depends(require_curator),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        c = await curation.validate(session, candidate_id, by=curator.email)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="introuvable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return c.to_dict()


@router.post("/candidates/{candidate_id}/reject", summary="Rejeter un candidat (humain)")
async def reject_candidate(
    candidate_id: str,
    curator: Principal = Depends(require_curator),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        c = await curation.reject(session, candidate_id, by=curator.email)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="introuvable") from exc
    await session.commit()
    return c.to_dict()
