"""Audit des requêtes Cortex → Box (Polaris-8).

Chaque appel d'un consultant Polaris (depuis Zolacortex) à une Zolabox cliente
est journalisé dans `audit.log` chez le client. Le trigger SQL côté DB calcule
automatiquement `payload_hash`, `prev_hash` et `row_hash` → chaîne immuable.

L'audit est **inviolable au niveau applicatif** : on insère via SQL paramétré ;
le `forbid_mutation` trigger interdit toute modification ultérieure.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.missions.tokens import MissionClaims

_log = get_logger("zolaos.missions.audit")


async def audit_box_access(
    *,
    session: AsyncSession,
    claims: MissionClaims,
    event: str,
    request_id: uuid.UUID,
    payload_extra: dict[str, Any] | None = None,
    severity: str = "info",
) -> None:
    """Trace une requête Cortex → Box dans `audit.log`.

    Le payload contient au minimum `mission_id`, `cabinet_tenant_id`,
    `consultant_user_id`, `scope_tags` et `offre`. `payload_extra` permet d'y
    ajouter les détails métier (query, hits_count, schema RAG…).
    """
    payload: dict[str, Any] = {
        "mission_id": str(claims.mission_id),
        "cabinet_tenant_id": str(claims.cabinet_tenant_id),
        "consultant_user_id": str(claims.consultant_user_id),
        "scope_tags": claims.scope_tags,
        "offre": claims.offre,
    }
    if payload_extra:
        payload.update(payload_extra)

    # Insertion brute via SQL : le trigger SQL chargera les hashes.
    await session.execute(
        text(
            """
            INSERT INTO audit.log
              (category, event, actor_type, actor_id, tenant_id, request_id, severity, payload)
            VALUES
              ('rag_access', :event, 'user', :actor, :tenant, :req, :sev, CAST(:payload AS jsonb))
            """
        ),
        {
            "event": event,
            "actor": str(claims.consultant_user_id),
            "tenant": str(claims.client_tenant_id),
            "req": str(request_id),
            "sev": severity,
            "payload": __import__("json").dumps(payload),
        },
    )
    await session.flush()
    _log.info(
        "audit.box_access",
        audit_event=event,
        mission_id=str(claims.mission_id),
        request_id=str(request_id),
    )
