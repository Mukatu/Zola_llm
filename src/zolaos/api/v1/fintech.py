"""Endpoints Fintech déterministes (profil box) — scoring crédit & KYC/AML.

Aide à la décision **explicable** : les moteurs restituent facteurs et alertes.
Aucune donnée n'est persistée à ce stade (calcul sur le corps de requête) ; la
persistance (dossiers de crédit, registres KYC) viendra dans un lot ultérieur.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zolaos.agents.fintech.kyc import (
    KycProfile,
    Transaction,
    evaluate_aml,
    evaluate_kyc,
)
from zolaos.agents.fintech.scoring import CreditRequest, ScoringBareme, score_credit

router = APIRouter(prefix="/v1/fintech", tags=["fintech"])


class ScoreRequest(BaseModel):
    dossier: CreditRequest
    bareme: ScoringBareme | None = None


@router.post("/score", summary="Scoring de crédit déterministe (aide à la décision)")
def fintech_score(req: ScoreRequest) -> dict[str, Any]:
    result = score_credit(req.dossier, req.bareme)
    return result.model_dump(mode="json")


@router.post("/kyc", summary="Évaluation KYC : complétude, risque, vigilance")
def fintech_kyc(profile: KycProfile) -> dict[str, Any]:
    return evaluate_kyc(profile).model_dump(mode="json")


class AmlRequest(BaseModel):
    transactions: list[Transaction] = Field(default_factory=list)


@router.post("/aml", summary="Surveillance AML : seuils, structuration, espèces")
def fintech_aml(req: AmlRequest) -> dict[str, Any]:
    return evaluate_aml(req.transactions).model_dump(mode="json")
