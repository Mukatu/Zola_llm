"""Journal d'audit du cabinet — consultation (Zolacortex).

Réservé au profil **cortex** et au rôle **admin**. Lecture seule sur la table
canonique **`audit.log`** (chaîne de hachage + immuabilité par triggers, cf.
`infra/postgres/02_audit_log.sql`) — on ne duplique pas le journal.

Par défaut on montre les catégories de **gouvernance** (actions humaines :
`security` = licences/comptes/credentials, `config`, `auth` = missions), en
écartant le bruit machine (accès RAG, appels d'agents). `category=all` lève ce
filtre. Filtres additionnels : événement, acteur, tenant.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import require_admin
from zolaos.audit import ACTIONS
from zolaos.core.profiles import require_cortex
from zolaos.db.session import get_session

router = APIRouter(
    prefix="/v1/cortex/audit",
    tags=["cortex", "audit"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)

# Catégories « gouvernance » (actions humaines auditées) montrées par défaut.
_GOVERNANCE_CATEGORIES = ("security", "config", "auth")


class AuditEventOut(BaseModel):
    id: int
    occurred_at: datetime
    category: str
    event: str
    actor_type: str
    actor_id: str | None
    tenant_id: str | None
    severity: str
    payload: dict[str, Any]


def _payload_dict(raw: Any) -> dict[str, Any]:
    # asyncpg peut renvoyer le jsonb en str selon le codec → on normalise en dict.
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw or {}


@router.get("/actions", response_model=list[str], summary="Référentiel des actions auditées")
async def list_actions() -> list[str]:
    """Verbes d'événement connus — peuple le filtre du cockpit."""
    return list(ACTIONS)


@router.get("", response_model=list[AuditEventOut], summary="Journal d'audit (anté-chronologique)")
async def list_audit(
    category: str | None = Query(
        default=None, description="Catégorie précise, ou 'all' pour tout ; défaut = gouvernance"
    ),
    event: str | None = Query(default=None, description="Filtre par verbe d'événement"),
    actor_id: str | None = Query(default=None, description="Filtre par identifiant d'acteur"),
    tenant_id: str | None = Query(default=None, description="Filtre par tenant concerné"),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventOut]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    if category == "all":
        pass  # aucun filtre de catégorie
    elif category is not None:
        clauses.append("category = :category")
        params["category"] = category
    else:
        clauses.append("category = ANY(:cats)")
        params["cats"] = list(_GOVERNANCE_CATEGORIES)

    if event is not None:
        clauses.append("event = :event")
        params["event"] = event
    if actor_id is not None:
        clauses.append("actor_id = :actor_id")
        params["actor_id"] = actor_id
    if tenant_id is not None:
        clauses.append("tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    # Fragments de clause STATIQUES (contrôlés ici) ; toutes les valeurs sont des
    # paramètres liés → pas d'injection malgré la concaténation.
    cols = "id, occurred_at, category, event, actor_type, actor_id, tenant_id, severity, payload"
    order = " ORDER BY occurred_at DESC, id DESC LIMIT :limit"
    query = f"SELECT {cols} FROM audit.log{where}{order}"  # noqa: S608
    rows = (await session.execute(text(query), params)).mappings().all()

    return [
        AuditEventOut(
            id=r["id"],
            occurred_at=r["occurred_at"],
            category=r["category"],
            event=r["event"],
            actor_type=r["actor_type"],
            actor_id=r["actor_id"],
            tenant_id=r["tenant_id"],
            severity=r["severity"],
            payload=_payload_dict(r["payload"]),
        )
        for r in rows
    ]
