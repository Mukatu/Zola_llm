"""Endpoints Fintech (profil box) — scoring crédit & KYC/AML.

- Calcul « à la volée » (sans persistance) : ``/score``, ``/kyc``, ``/aml``.
- Persistance (FINTECH-3) : dossiers de crédit (``/applications``) et registres
  KYC (``/kyc-records``) — l'évaluation déterministe est figée à la création,
  puis un workflow de décision humaine porte le ``statut``. Multi-tenant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.fintech.kyc import (
    KycProfile,
    Transaction,
    evaluate_aml,
    evaluate_kyc,
)
from zolaos.agents.fintech.scoring import CreditRequest, ScoringBareme, score_credit
from zolaos.db.session import get_session
from zolaos.db.store_repo import CreditApplicationRepository, KycRecordRepository

router = APIRouter(prefix="/v1/fintech", tags=["fintech"])

_STATUTS_CREDIT = {"evaluee", "accordee", "refusee", "decaissee", "cloturee"}
_STATUTS_KYC = {"a_valider", "valide", "refuse"}


# ------------------------------------------------------------- calcul à la volée


class ScoreRequest(BaseModel):
    dossier: CreditRequest
    bareme: ScoringBareme | None = None


@router.post("/score", summary="Scoring de crédit déterministe (aide à la décision)")
def fintech_score(req: ScoreRequest) -> dict[str, Any]:
    return score_credit(req.dossier, req.bareme).model_dump(mode="json")


@router.post("/kyc", summary="Évaluation KYC : complétude, risque, vigilance")
def fintech_kyc(profile: KycProfile) -> dict[str, Any]:
    return evaluate_kyc(profile).model_dump(mode="json")


class AmlRequest(BaseModel):
    transactions: list[Transaction] = Field(default_factory=list)


@router.post("/aml", summary="Surveillance AML : seuils, structuration, espèces")
def fintech_aml(req: AmlRequest) -> dict[str, Any]:
    return evaluate_aml(req.transactions).model_dump(mode="json")


# ------------------------------------------------------------ dossiers de crédit


class ApplicationCreate(BaseModel):
    client: str
    dossier: CreditRequest
    numero: str | None = None
    bareme: ScoringBareme | None = None


class DecisionIn(BaseModel):
    statut: str
    commentaire: str | None = None


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
    summary="Évaluer et enregistrer un dossier de crédit",
)
async def create_application(
    body: ApplicationCreate,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    res = score_credit(body.dossier, body.bareme)
    numero = body.numero or f"CR-{int(datetime.now(UTC).timestamp())}"
    rec = await CreditApplicationRepository(session).create(
        {
            "tenant_id": tenant_id,
            "numero": numero,
            "client": body.client,
            "montant_demande_xaf": body.dossier.montant_demande_xaf,
            "duree_mois": body.dossier.duree_mois,
            "score": res.score,
            "grade": res.grade,
            "decision": res.decision,
            "statut": "evaluee",
            "taux_endettement_pct": res.taux_endettement_pct,
            "mensualite_xaf": res.mensualite_estimee_xaf,
            "montant_max_xaf": res.montant_max_suggere_xaf,
            "dossier": body.dossier.model_dump(mode="json"),
            "resultat": res.model_dump(mode="json"),
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("/applications", summary="Lister les dossiers de crédit")
async def list_applications(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await CreditApplicationRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"applications": [r.to_dict() for r in rows]}


@router.get("/applications/{app_id}", summary="Lire un dossier de crédit")
async def get_application(
    app_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CreditApplicationRepository(session).get(app_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    return rec.to_dict()


@router.post("/applications/{app_id}/decision", summary="Décision/suivi d'un dossier")
async def decide_application(
    app_id: str,
    body: DecisionIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.statut not in _STATUTS_CREDIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"statut_invalide (attendu : {sorted(_STATUTS_CREDIT)})",
        )
    rec = await CreditApplicationRepository(session).update(
        app_id, tenant_id=tenant_id, fields={"statut": body.statut, "commentaire": body.commentaire}
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/applications/{app_id}", summary="Supprimer un dossier de crédit")
async def delete_application(
    app_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await CreditApplicationRepository(session).delete(app_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="application_not_found")
    await session.commit()
    return {"status": "deleted"}


# --------------------------------------------------------------- registres KYC


@router.post(
    "/kyc-records",
    status_code=status.HTTP_201_CREATED,
    summary="Évaluer et enregistrer un dossier KYC",
)
async def create_kyc_record(
    profile: KycProfile,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    res = evaluate_kyc(profile)
    rec = await KycRecordRepository(session).create(
        {
            "tenant_id": tenant_id,
            "nom": profile.nom,
            "type_client": profile.type_client,
            "niveau_risque": res.niveau_risque,
            "score_risque": res.score_risque,
            "vigilance": res.vigilance,
            "complet": res.complet,
            "peut_entrer_en_relation": res.peut_entrer_en_relation,
            "pep": profile.pep,
            "statut": "a_valider",
            "profil": profile.model_dump(mode="json"),
            "resultat": res.model_dump(mode="json"),
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("/kyc-records", summary="Lister les dossiers KYC")
async def list_kyc_records(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await KycRecordRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"kyc_records": [r.to_dict() for r in rows]}


@router.post("/kyc-records/{rec_id}/decision", summary="Décision conformité d'un dossier KYC")
async def decide_kyc_record(
    rec_id: str,
    body: DecisionIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.statut not in _STATUTS_KYC:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"statut_invalide (attendu : {sorted(_STATUTS_KYC)})",
        )
    rec = await KycRecordRepository(session).update(
        rec_id, tenant_id=tenant_id, fields={"statut": body.statut, "commentaire": body.commentaire}
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kyc_record_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/kyc-records/{rec_id}", summary="Supprimer un dossier KYC")
async def delete_kyc_record(
    rec_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await KycRecordRepository(session).delete(rec_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="kyc_record_not_found")
    await session.commit()
    return {"status": "deleted"}
