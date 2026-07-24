"""Cyber-défense — audit de durcissement **défensif** (CYBER-1).

Profil box. Déterministe : le moteur `auditer()` score une base de durcissement
sur des faits de configuration **déclarés** ; aucune action active, aucun scan,
aucune capacité offensive. Endpoints : calcul à la volée (`/audit`) + registre
persisté (`/audits`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.cyber.anomalies import LogEvent, ParamsDetection, detecter_anomalies
from zolaos.agents.cyber.hardening import BASELINE, ConfigAudit, Controle, auditer
from zolaos.db.session import get_session
from zolaos.db.store_repo import (
    CyberAuditRepository,
    CyberDetectionRepository,
    CyberParamsRepository,
)

router = APIRouter(prefix="/v1/cyber", tags=["cyber"])

_STATUTS_DETECTION = {"a_examiner", "classee", "traitee"}


# ============ Paramètres gouvernés : base de durcissement + seuils (CYBER-3) ============


def _cyber_defaults() -> dict[str, Any]:
    """Graine = constantes du moteur (seuils par défaut + base de durcissement)."""
    return {
        "seuils": ParamsDetection().model_dump(),
        "controles": {
            c.cle: {"severite": c.severite, "active": True, "libelle": c.libelle} for c in BASELINE
        },
    }


async def _effective_cyber(
    session: AsyncSession, tenant_id: str, country: str
) -> tuple[ParamsDetection, list[Controle], dict[str, Any]]:
    """Paramètres effectifs = graine surchargée par l'override tenant.

    Retourne (seuils d'anomalies, base de durcissement effective, vue JSON avec
    statut de validation).
    """
    defaults = _cyber_defaults()
    rec = await CyberParamsRepository(session).get(tenant_id=tenant_id, country=country)
    payload = rec.payload if rec is not None else {}

    seuils = {**defaults["seuils"], **(payload.get("seuils") or {})}
    params = ParamsDetection(**seuils)

    ctrl_over = payload.get("controles") or {}
    controles: list[Controle] = []
    controles_view: list[dict[str, Any]] = []
    for c in BASELINE:
        ov = ctrl_over.get(c.cle) or {}
        active = bool(ov.get("active", True))
        severite = ov.get("severite", c.severite)
        controles_view.append(
            {
                "cle": c.cle,
                "libelle": c.libelle,
                "fonction": c.fonction,
                "severite": severite,
                "active": active,
            }
        )
        if active:
            controles.append(c.model_copy(update={"severite": severite}))

    view = {
        "seuils": seuils,
        "controles": controles_view,
        "source_donnees": "tenant" if rec is not None else "defaut",
        "validated": rec.validated if rec is not None else True,
        "validated_by": rec.validated_by if rec is not None else "",
        "validated_at": (
            rec.validated_at.isoformat() if rec is not None and rec.validated_at else None
        ),
    }
    return params, controles, view


@router.get("/params", summary="Paramètres gouvernés : seuils + base de durcissement")
async def get_cyber_params(
    country: str = "cg",
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, _, view = await _effective_cyber(session, tenant_id, country)
    return view


class CyberParamsEdit(BaseModel):
    seuils: dict[str, int] | None = None
    controles: dict[str, dict[str, Any]] | None = None


@router.put("/params", summary="Éditer les paramètres (override) — re-validation requise")
async def edit_cyber_params(
    body: CyberParamsEdit,
    country: str = "cg",
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if body.seuils is not None:
        payload["seuils"] = body.seuils
    if body.controles is not None:
        payload["controles"] = body.controles
    version = f"custom-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    await CyberParamsRepository(session).upsert(
        tenant_id=tenant_id, country=country, version=version, payload=payload
    )
    await session.commit()
    _, _, view = await _effective_cyber(session, tenant_id, country)
    return view


class CyberParamsValidation(BaseModel):
    validated: bool
    validated_by: str = ""
    note: str = ""


@router.post("/params/validate", summary="Valider / révoquer les paramètres")
async def validate_cyber_params(
    body: CyberParamsValidation,
    country: str = "cg",
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CyberParamsRepository(session).set_validation(
        tenant_id=tenant_id,
        country=country,
        validated=body.validated,
        validated_by=body.validated_by,
        note=body.note,
    )
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="aucun_parametre_tenant_a_valider"
        )
    await session.commit()
    _, _, view = await _effective_cyber(session, tenant_id, country)
    return view


@router.get("/baseline", summary="Base de durcissement (contrôles évalués)")
def cyber_baseline() -> dict[str, Any]:
    return {
        "controles": [c.model_dump() for c in BASELINE],
        "reference_cadre": (
            "Base indicative (inspirée CIS / ANSSI / NIST CSF) — défensive, à adapter."
        ),
    }


@router.post("/audit", summary="Audit de durcissement (calcul à la volée, sans persistance)")
async def cyber_audit(
    config: ConfigAudit,
    tenant_id: str = "local",
    country: str = "cg",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, controles, _ = await _effective_cyber(session, tenant_id, country)
    return auditer(config, controles=controles).model_dump(mode="json")


class CyberAuditCreate(BaseModel):
    cible: str
    config: ConfigAudit


@router.post(
    "/audits",
    status_code=status.HTTP_201_CREATED,
    summary="Évaluer et enregistrer un audit de durcissement",
)
async def create_cyber_audit(
    body: CyberAuditCreate,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, controles, _ = await _effective_cyber(session, tenant_id, "cg")
    res = auditer(body.config, controles=controles)
    rec = await CyberAuditRepository(session).create(
        {
            "tenant_id": tenant_id,
            "cible": body.cible,
            "score_conformite": Decimal(res.score_conformite),
            "nb_conforme": res.nb_conforme,
            "nb_non_conforme": res.nb_non_conforme,
            "nb_a_verifier": res.nb_a_verifier,
            "niveau": res.niveau,
            "config": body.config.model_dump(),
            "resultat": res.model_dump(mode="json"),
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("/audits", summary="Lister les audits de durcissement")
async def list_cyber_audits(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await CyberAuditRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"audits": [r.to_dict() for r in rows]}


@router.get("/audits/{audit_id}", summary="Lire un audit de durcissement")
async def get_cyber_audit(
    audit_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CyberAuditRepository(session).get(audit_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_not_found")
    return rec.to_dict()


@router.delete("/audits/{audit_id}", summary="Supprimer un audit de durcissement")
async def delete_cyber_audit(
    audit_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await CyberAuditRepository(session).delete(audit_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_not_found")
    await session.commit()
    return {"status": "deleted"}


# ==================== Détection d'anomalies sur journaux (CYBER-2) ====================


class AnomaliesRequest(BaseModel):
    events: list[LogEvent] = []
    params: ParamsDetection | None = None


@router.post("/anomalies", summary="Détecter des anomalies (à la volée, sans persistance)")
async def cyber_anomalies(
    req: AnomaliesRequest,
    tenant_id: str = "local",
    country: str = "cg",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    params = req.params
    if params is None:
        params, _, _ = await _effective_cyber(session, tenant_id, country)
    return detecter_anomalies(req.events, params).model_dump(mode="json")


class CyberDetectionCreate(BaseModel):
    cible: str
    events: list[LogEvent] = []
    params: ParamsDetection | None = None


class DetectionDecisionIn(BaseModel):
    statut: str
    commentaire: str | None = None


@router.post(
    "/detections",
    status_code=status.HTTP_201_CREATED,
    summary="Analyser des journaux et enregistrer la détection",
)
async def create_cyber_detection(
    body: CyberDetectionCreate,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    params = body.params
    if params is None:
        params, _, _ = await _effective_cyber(session, tenant_id, "cg")
    res = detecter_anomalies(body.events, params)
    rec = await CyberDetectionRepository(session).create(
        {
            "tenant_id": tenant_id,
            "cible": body.cible,
            "nb_events": res.nb_events,
            "nb_anomalies": len(res.anomalies),
            "niveau": res.niveau,
            "statut": "a_examiner",
            "params": params.model_dump(),
            "resultat": res.model_dump(mode="json"),
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("/detections", summary="Lister les détections d'anomalies")
async def list_cyber_detections(
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await CyberDetectionRepository(session).list(tenant_id=tenant_id)
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return {"detections": [r.to_dict() for r in rows]}


@router.get("/detections/{detection_id}", summary="Lire une détection")
async def get_cyber_detection(
    detection_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await CyberDetectionRepository(session).get(detection_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="detection_not_found")
    return rec.to_dict()


@router.post(
    "/detections/{detection_id}/decision", summary="Traiter une détection (classer / traiter)"
)
async def decide_cyber_detection(
    detection_id: str,
    body: DetectionDecisionIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.statut not in _STATUTS_DETECTION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"statut_invalide (attendu : {sorted(_STATUTS_DETECTION)})",
        )
    rec = await CyberDetectionRepository(session).update(
        detection_id,
        tenant_id=tenant_id,
        fields={"statut": body.statut, "commentaire": body.commentaire},
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="detection_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/detections/{detection_id}", summary="Supprimer une détection")
async def delete_cyber_detection(
    detection_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    ok = await CyberDetectionRepository(session).delete(detection_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="detection_not_found")
    await session.commit()
    return {"status": "deleted"}
