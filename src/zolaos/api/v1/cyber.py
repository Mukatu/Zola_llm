"""Cyber-défense — audit de durcissement **défensif** (CYBER-1).

Profil box. Déterministe : le moteur `auditer()` score une base de durcissement
sur des faits de configuration **déclarés** ; aucune action active, aucun scan,
aucune capacité offensive. Endpoints : calcul à la volée (`/audit`) + registre
persisté (`/audits`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.cyber.hardening import BASELINE, ConfigAudit, auditer
from zolaos.db.session import get_session
from zolaos.db.store_repo import CyberAuditRepository

router = APIRouter(prefix="/v1/cyber", tags=["cyber"])


@router.get("/baseline", summary="Base de durcissement (contrôles évalués)")
def cyber_baseline() -> dict[str, Any]:
    return {
        "controles": [c.model_dump() for c in BASELINE],
        "reference_cadre": (
            "Base indicative (inspirée CIS / ANSSI / NIST CSF) — défensive, à adapter."
        ),
    }


@router.post("/audit", summary="Audit de durcissement (calcul à la volée, sans persistance)")
def cyber_audit(config: ConfigAudit) -> dict[str, Any]:
    return auditer(config).model_dump(mode="json")


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
    res = auditer(body.config)
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
