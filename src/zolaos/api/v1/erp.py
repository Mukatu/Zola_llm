"""Endpoints déterministes ERP / pilotage opérationnel (FE↔BE).

Expose les **moteurs déterministes** (calculs exacts, sans LLM) consommés par
les écrans de capacité du frontend : paie, validation d'écritures, supply chain,
achats, facility, HSE. Profil **box** (capacités côté client, données locales).

Tous les calculs restent **côté code** ; le LLM (rédaction/synthèse) passe par
les agents via `/v1/query`. Ici : entrée JSON structurée → sortie structurée.
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from zolaos.agents.erp.achats import OffreFournisseur, Supplier, comparer_offres, score_fournisseur, verifier_conformite
from zolaos.agents.erp.compta import ChartOfAccounts, JournalValidator
from zolaos.agents.erp.facility import Asset, Echeance, echeances_dues, maintenances_dues
from zolaos.agents.erp.hse import Risque, cartographie_risques
from zolaos.agents.erp.payroll import PayrollCalculator, PayrollScaleNotValidated, load_payroll_scale
from zolaos.agents.erp.supply import StockItem, analyser_reappro, alertes_rupture
from zolaos.connectors.models import JournalEntry

router = APIRouter(prefix="/v1/erp", tags=["erp"])

_payroll = PayrollCalculator()


# ---------------------------------------------------------------- Paie

class PayrollRequest(BaseModel):
    brut_mensuel_xaf: Decimal = Field(..., ge=0)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")
    allow_unvalidated: bool = Field(default=False, description="Simulation explicite si barème non validé")


@router.post("/payroll/compute", summary="Calcul de bulletin de paie (déterministe)")
def payroll_compute(req: PayrollRequest) -> dict[str, Any]:
    scale = load_payroll_scale(req.country)
    try:
        result = _payroll.compute(req.brut_mensuel_xaf, scale=scale, allow_unvalidated=req.allow_unvalidated)
    except PayrollScaleNotValidated as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"bareme_non_valide: {exc}. Passer allow_unvalidated=true pour une simulation.",
        ) from exc
    return asdict(result)


# ---------------------------------------------------------------- Compta

@router.post("/compta/validate", summary="Validation d'écriture SYSCOHADA (déterministe)")
def compta_validate(entry: JournalEntry) -> dict[str, Any]:
    report = JournalValidator(ChartOfAccounts.load(entry.country)).validate(entry)
    return asdict(report)


# ---------------------------------------------------------------- Supply Chain

class SupplyRequest(BaseModel):
    items: list[StockItem]
    horizon_jours: int = Field(default=30, ge=1, le=365)


@router.post("/supply/analyze", summary="Analyse de réappro + alertes rupture (déterministe)")
def supply_analyze(req: SupplyRequest) -> dict[str, Any]:
    return {
        "suggestions": [asdict(s) for s in analyser_reappro(req.items)],
        "alertes": [asdict(a) for a in alertes_rupture(req.items, horizon_jours=req.horizon_jours)],
    }


# ---------------------------------------------------------------- Achats

class AchatsCompareRequest(BaseModel):
    offres: list[OffreFournisseur]


@router.post("/achats/compare", summary="Comparaison de devis (déterministe)")
def achats_compare(req: AchatsCompareRequest) -> dict[str, Any]:
    return {"classement": [asdict(c) for c in comparer_offres(req.offres)]}


@router.post("/achats/supplier-score", summary="Scoring fournisseur + conformité (déterministe)")
def achats_supplier_score(supplier: Supplier) -> dict[str, Any]:
    return {
        "score": asdict(score_fournisseur(supplier)),
        "conformite_manquante": verifier_conformite(supplier),
    }


# ---------------------------------------------------------------- Facility

class FacilityRequest(BaseModel):
    assets: list[Asset] = Field(default_factory=list)
    echeances: list[Echeance] = Field(default_factory=list)
    horizon_jours: int = Field(default=30, ge=1, le=365)


@router.post("/facility/echeancier", summary="Maintenances + échéances dues (déterministe)")
def facility_echeancier(req: FacilityRequest) -> dict[str, Any]:
    return {
        "maintenances": [asdict(a) for a in maintenances_dues(req.assets, horizon_jours=req.horizon_jours)],
        "echeances": [asdict(a) for a in echeances_dues(req.echeances, horizon_jours=req.horizon_jours)],
    }


# ---------------------------------------------------------------- HSE

class HseRequest(BaseModel):
    risques: list[Risque]


@router.post("/hse/cartographie", summary="Cartographie des risques (déterministe)")
def hse_cartographie(req: HseRequest) -> dict[str, Any]:
    return {"risques": [asdict(r) for r in cartographie_risques(req.risques)]}
