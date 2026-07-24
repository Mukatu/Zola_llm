"""Opérations de persistance du pipeline de contribution (Phase A).

- consentement (opt-in) local par locataire ;
- extraction **idempotente** (flag `contributed`) du feedback → quarantaine
  (candidats anonymisés, sans lien locataire). Aucune promotion.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.commons.anonymize import content_hash, origin_hash
from zolaos.commons.extraction import feedback_to_candidate, scope_allowed
from zolaos.commons.learned import rule_key
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
    oh = origin_hash(tenant_id)  # empreinte anonyme du locataire (k-anonymat)
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
                    origins=[oh],
                    occurrences=1,
                )
            )
            nouveaux += 1
        elif oh not in (existing.origins or []):
            # Nouvelle origine distincte → renforce la corroboration (k-anonymat).
            existing.origins = [*(existing.origins or []), oh]
            existing.occurrences = len(existing.origins)
            corrobores += 1

    await session.flush()
    return {"scanned": len(feedbacks), "nouveaux": nouveaux, "corrobores": corrobores}


async def _upsert_candidate(
    session: AsyncSession, *, ctype: str, domaine: str, payload: dict[str, Any], oh: str
) -> str:
    """Insère (ou corrobore) un candidat en quarantaine. Retourne l'état."""
    ch = content_hash(payload)
    existing = (
        await session.execute(select(ContribCandidate).where(ContribCandidate.content_hash == ch))
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            ContribCandidate(
                type=ctype,
                domaine=domaine,
                payload=payload,
                content_hash=ch,
                origins=[oh],
                occurrences=1,
            )
        )
        return "nouveau"
    if oh not in (existing.origins or []):
        existing.origins = [*(existing.origins or []), oh]
        existing.occurrences = len(existing.origins)
        return "corrobore"
    return "connu"


async def capture_categorisation(
    session: AsyncSession,
    tenant_id: str,
    *,
    libelle: str,
    valeur: str,
    domaine: str = "erp.compta",
) -> dict[str, Any]:
    """Capture une correction (ex. libellé → compte) comme candidat ``categorisation``.

    Gaté par l'opt-in du locataire et son périmètre. La clé est anonymisée avant
    d'entrer en quarantaine (I2). Rien n'est promu ici (Phases B/C).
    """
    optin = await get_optin(session, tenant_id)
    enabled = bool(optin and optin.enabled)
    scopes = list(optin.scopes) if optin else []
    if not scope_allowed(enabled, scopes, domaine):
        return {"captured": False, "raison": "opt-in désactivé pour ce périmètre"}

    cle = rule_key(libelle)
    if not cle or not valeur.strip():
        return {"captured": False, "raison": "libellé/valeur vide"}

    payload = {"domaine": domaine, "cle": cle, "valeur": valeur.strip()}
    etat = await _upsert_candidate(
        session, ctype="categorisation", domaine=domaine, payload=payload, oh=origin_hash(tenant_id)
    )
    await session.flush()
    return {"captured": True, "etat": etat}
