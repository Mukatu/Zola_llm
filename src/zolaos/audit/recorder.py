"""Enregistrement d'une action sensible du cabinet dans le journal canonique.

On écrit dans **`audit.log`** (schéma `audit`) — la source de vérité déjà utilisée
pour l'audit des accès RAG et des missions : chaîne de hachage (`payload_hash`/
`prev_hash`/`row_hash` via trigger) + immuabilité (triggers `forbid_mutation`).
On NE crée PAS de table parallèle. L'insert se fait dans la session **courante** :
la trace est committée dans la MÊME transaction que l'action qu'elle décrit.

Catégorie `security` (gouvernance : licences, comptes, credentials de box). Les
verbes sont normalisés (`ACTIONS`) pour un filtrage fiable côté cockpit.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal

# Verbes des actions cabinet auditées (+ les événements de mission déjà écrits
# nativement par `api/v1/cortex.py`). Sert de référentiel au filtre du cockpit.
ACTIONS: tuple[str, ...] = (
    "license.issued",
    "license.revoked",
    "account.created",
    "account.updated",
    "account.password_reset",
    "client.created",
    "box_credential.issued",
    "box_credential.revoked",
    "mission_created",
    "mission_revoked",
)

# Catégorie `audit.log` des actions de gouvernance cabinet (parmi le jeu fermé
# défini dans 02_audit_log.sql : auth/query/agent_call/rag_access/tool_call/
# security/fallback/config).
_CATEGORY = "security"


async def record_audit(
    session: AsyncSession,
    *,
    actor: Principal | None,
    action: str,
    summary: str,
    target_type: str | None = None,
    target_id: Any = None,
    extra: dict[str, Any] | None = None,
    request: Request | None = None,
    severity: str = "info",
) -> None:
    """Insère une action cabinet dans `audit.log` (committée avec l'action appelante).

    `actor` : le `Principal` admin auteur. `target_*` : l'objet visé (le `tenant_id`
    du journal reçoit la cible quand c'est un tenant → filtrage par client). `extra` :
    détail structuré (tier/modules, rôle…). `request` : source (IP)."""
    ip: str | None = None
    if request is not None and request.client is not None:
        ip = request.client.host

    payload: dict[str, Any] = {
        "summary": summary,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "actor_email": actor.email if actor is not None else None,
        "ip": ip,
    }
    if extra:
        payload.update(extra)

    # tenant_id du journal = la cible quand c'est un tenant (filtrage par client).
    audit_tenant = str(target_id) if (target_type == "tenant" and target_id is not None) else None

    # Insert brut : le trigger BEFORE INSERT calcule les hashes de la chaîne.
    await session.execute(
        text(
            """
            INSERT INTO audit.log
              (category, event, actor_type, actor_id, tenant_id, request_id, severity, payload)
            VALUES
              (:cat, :event, 'user', :actor, :tenant, :rid, :sev, CAST(:payload AS jsonb))
            """
        ),
        {
            "cat": _CATEGORY,
            "event": action,
            "actor": str(actor.user_id) if actor is not None else "system",
            "tenant": audit_tenant,
            "rid": str(uuid.uuid4()),
            "sev": severity,
            "payload": json.dumps(payload),
        },
    )
