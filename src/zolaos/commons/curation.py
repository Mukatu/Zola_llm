"""Gouvernance de la contribution (Phase B) — pré-filtre auto + décision humaine.

Curation **mixte** : le pré-filtre automatique n'expose au curateur que les
candidats **en attente** et **corroborés** (≥ k origines distinctes, I3). La
validation/le rejet restent **humains** (I5). Aucune promotion ici — un candidat
validé attend la Phase C.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.store_models import ContribCandidate

K_ANONYMITY = 3  # origines distinctes requises avant éligibilité à la revue humaine


def is_eligible(candidate: ContribCandidate) -> bool:
    """Éligible à la validation humaine : en attente ET corroboré ≥ k (pré-filtre auto)."""
    return candidate.status == "pending" and candidate.occurrences >= K_ANONYMITY


async def list_candidates(
    session: AsyncSession,
    *,
    status: str | None = "pending",
    eligible_only: bool = True,
    limit: int = 200,
) -> list[ContribCandidate]:
    stmt = (
        select(ContribCandidate)
        .order_by(ContribCandidate.occurrences.desc(), ContribCandidate.first_seen)
        .limit(limit)
    )
    if status:
        stmt = stmt.where(ContribCandidate.status == status)
    rows = list((await session.execute(stmt)).scalars().all())
    if eligible_only:
        rows = [c for c in rows if c.occurrences >= K_ANONYMITY]
    return rows


async def validate(session: AsyncSession, candidate_id: str, *, by: str) -> ContribCandidate:
    """Valide un candidat éligible (humain). Ne promeut PAS (Phase C)."""
    c = await session.get(ContribCandidate, candidate_id)
    if c is None:
        raise KeyError(candidate_id)
    if not is_eligible(c):
        raise ValueError("candidat non éligible (k-anonymat non atteint ou déjà traité)")
    c.status = "validated"
    c.validated_by = by
    c.validated_at = datetime.now(UTC)
    await session.flush()
    return c


async def reject(session: AsyncSession, candidate_id: str, *, by: str) -> ContribCandidate:
    """Rejette un candidat (humain)."""
    c = await session.get(ContribCandidate, candidate_id)
    if c is None:
        raise KeyError(candidate_id)
    c.status = "rejected"
    c.validated_by = by
    c.validated_at = datetime.now(UTC)
    await session.flush()
    return c
