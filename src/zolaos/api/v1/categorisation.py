"""Endpoint d'auto-catégorisation comptable (libellé → compte SYSCOHADA).

Profil box. Suggestion **déterministe** (moteur de règles filtré contre le plan
de comptes) enrichie des **règles apprises** du communs (niveau 3). Une correction
de l'utilisateur peut être capturée (opt-in) pour alimenter le communs.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.categorisation import suggest_accounts
from zolaos.agents.erp.compta import ChartOfAccounts
from zolaos.api.auth import Principal, authenticate
from zolaos.commons import learned
from zolaos.commons.pipeline import capture_categorisation
from zolaos.db.session import get_session

router = APIRouter(prefix="/v1/erp", tags=["erp"])

_DOMAINE = "erp.compta"


class SuggestRequest(BaseModel):
    libelle: str = Field(..., min_length=1)
    sens: str | None = Field(default=None, pattern=r"^(debit|credit)$")
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@router.post("/compta/suggest", summary="Auto-catégorisation : libellé vers compte SYSCOHADA")
async def compta_suggest(
    req: SuggestRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    chart = ChartOfAccounts.load(req.country)
    regles = await learned.lookup(session, _DOMAINE, req.libelle)
    suggestions = suggest_accounts(
        req.libelle, chart=chart, sens=req.sens, learned_comptes=[r.valeur for r in regles]
    )
    return {"suggestions": [asdict(s) for s in suggestions]}


class CorrectionRequest(BaseModel):
    libelle: str = Field(..., min_length=1)
    compte: str = Field(..., min_length=1)


@router.post("/compta/correction", summary="Enregistrer une correction (contribution opt-in)")
async def compta_correction(
    req: CorrectionRequest,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Capture la correction comme candidat ``categorisation`` (gaté par l'opt-in)."""
    tenant = principal.tenant_id or "local"
    res = await capture_categorisation(
        session, tenant, libelle=req.libelle, valeur=req.compte, domaine=_DOMAINE
    )
    await session.commit()
    return res
