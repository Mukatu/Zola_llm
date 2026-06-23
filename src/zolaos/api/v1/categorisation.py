"""Endpoint d'auto-catégorisation comptable (libellé → compte SYSCOHADA).

Profil box. Suggestion **déterministe** (moteur de règles filtré contre le plan
de comptes) ; le `JournalValidator` valide, l'humain confirme.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zolaos.agents.erp.categorisation import suggest_accounts
from zolaos.agents.erp.compta import ChartOfAccounts

router = APIRouter(prefix="/v1/erp", tags=["erp"])


class SuggestRequest(BaseModel):
    libelle: str = Field(..., min_length=1)
    sens: str | None = Field(default=None, pattern=r"^(debit|credit)$")
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@router.post("/compta/suggest", summary="Auto-catégorisation : libellé vers compte SYSCOHADA")
def compta_suggest(req: SuggestRequest) -> dict[str, Any]:
    chart = ChartOfAccounts.load(req.country)
    suggestions = suggest_accounts(req.libelle, chart=chart, sens=req.sens)
    return {"suggestions": [asdict(s) for s in suggestions]}
