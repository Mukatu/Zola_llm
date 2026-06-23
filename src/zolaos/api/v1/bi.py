"""Endpoints déterministes BI / Pilotage (FE↔BE) — KPIs cross-métiers.

Profil box. KPIs calculés en code (compute_kpis) à partir des données fournies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zolaos.agents.bi.kpi import compute_kpis
from zolaos.connectors.models import BankTransaction, Employee, Invoice

router = APIRouter(prefix="/v1/bi", tags=["bi"])


class BiRequest(BaseModel):
    invoices: list[Invoice] = Field(default_factory=list)
    transactions: list[BankTransaction] = Field(default_factory=list)
    employees: list[Employee] = Field(default_factory=list)
    periode: str | None = None


@router.post("/kpis", summary="KPIs déterministes cross-métiers")
def bi_kpis(req: BiRequest) -> dict[str, Any]:
    kpis = compute_kpis(
        invoices=req.invoices or None,
        transactions=req.transactions or None,
        employees=req.employees or None,
        periode=req.periode,
    )
    return {"kpis": [k.model_dump(mode="json") for k in kpis]}
