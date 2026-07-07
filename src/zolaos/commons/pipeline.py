"""Opérations de persistance du pipeline de contribution (Phase A).

- consentement (opt-in) local par locataire ;
- extraction **idempotente** (flag `contributed`) du feedback → quarantaine
  (candidats anonymisés, sans lien locataire). Aucune promotion.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.commons.extraction import feedback_to_candidate
from zolaos.db.store_models import AgentFeedbackRecord, ContribCandidate, ContributionOptin


async def get_optin(session: AsyncSession, tenant_id: str) -> ContributionOptin | None:
    return (
        await session.execute(
            select(ContributionOptin).where(ContributionOptin.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


async def set_optin(
    session: AsyncSession,
    tenant_id: str,
    *,
    enabled: bool,
    scopes: list[str],
    updated_by: str | None = None,
) -> ContributionOptin:
    row = await get_optin(session, tenant_id)
    if row is None:
        row = ContributionOptin(
            tenant_id=tenant_id, enabled=enabled, scopes=list(scopes), updated_by=updated_by
        )
        session.add(row)
    else:
        row.enabled = enabled
        row.scopes = list(scopes)
        row.updated_by = updated_by
    await session.flush()
    return row


async def run_extraction(session: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Extrait les candidats des feedbacks non encore traités de ce locataire.

    Idempotent (marque `contributed=True`). N'agit que si l'opt-in est actif ;
    respecte le périmètre consenti. Rien n'est promu — dépôt en quarantaine.
    """
    optin = await get_optin(session, tenant_id)
    if optin is None or not optin.enabled:
        return {"scanned": 0, "nouveaux": 0, "corrobores": 0, "raison": "opt-in désactivé"}

    scopes = list(optin.scopes or [])
    feedbacks = (
        (
            await session.execute(
                select(AgentFeedbackRecord).where(
                    AgentFeedbackRecord.tenant_id == tenant_id,
                    AgentFeedbackRecord.contributed.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )

    nouveaux = corrobores = 0
    for fb in feedbacks:
        cand = feedback_to_candidate(fb.to_dict(), enabled=optin.enabled, scopes=scopes)
        fb.contributed = True  # traité (qu'il produise un candidat ou non)
        if cand is None:
            continue
        existing = (
            await session.execute(
                select(ContribCandidate).where(ContribCandidate.content_hash == cand.content_hash)
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                ContribCandidate(
                    type=cand.type,
                    domaine=cand.domaine,
                    payload=cand.payload,
                    content_hash=cand.content_hash,
                )
            )
            nouveaux += 1
        else:
            existing.occurrences += 1
            corrobores += 1

    await session.flush()
    return {"scanned": len(feedbacks), "nouveaux": nouveaux, "corrobores": corrobores}
