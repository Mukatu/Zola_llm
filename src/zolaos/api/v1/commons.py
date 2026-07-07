"""Communs de connaissance (niveau 3) — consentement + extraction (Phase A).

Endpoints authentifiés, tenant dérivé de l'identité. Le client ouvre (ou ferme)
la contribution par périmètre ; l'extraction dépose des candidats **anonymisés**
en quarantaine. Aucune promotion vers le moteur (Phases B/C). Cf.
docs/COMMONS_PIPELINE.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate
from zolaos.commons.pipeline import get_optin, run_extraction, set_optin
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
