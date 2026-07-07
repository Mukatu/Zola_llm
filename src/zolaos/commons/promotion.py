"""Promotion des candidats validés vers le moteur (Phase C).

**Opération d'administration** (rôle migrator, hors chemin applicatif) : les
candidats `validated` (Phase B) sont ingérés dans le corpus partagé `rag_commons`
(consulté par les agents via le retrieval-union), marqués `promoted`, et tracés
dans un journal **anonyme**. Idempotent (source_uri stable + ON CONFLICT).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.store_models import CommonsAudit, ContribCandidate
from zolaos.rag.ingest import ingest_text
from zolaos.security.pii import PIIRedactionPolicy

TARGET_RAG = "rag_commons"


def _document_text(cand: ContribCandidate) -> str:
    p = cand.payload or {}
    q = str(p.get("question", "")).strip()
    r = str(p.get("reponse", "")).strip()
    return f"Question : {q}\n\nRéponse : {r}"


async def promote_validated(session: AsyncSession, *, limit: int = 500) -> dict[str, Any]:
    """Ingère les candidats validés dans rag_commons + journalise (session migrator)."""
    cands = (
        (
            await session.execute(
                select(ContribCandidate)
                .where(ContribCandidate.status == "validated")
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    promus = 0
    for c in cands:
        source_uri = f"commons://{c.domaine or 'general'}/{c.content_hash}"
        await ingest_text(
            text=_document_text(c),
            source_uri=source_uri,
            schema=TARGET_RAG,
            tags=[
                "country:cg",
                "source:contribution",
                f"type:{c.type}",
                f"domaine:{c.domaine}",
            ],
            pii_policy=PIIRedactionPolicy.NONE,  # déjà anonymisé en amont (Phase A)
            source_id=f"commons-{c.content_hash[:12]}",
            extra_metadata={
                "type": c.type,
                "domaine": c.domaine,
                "occurrences": c.occurrences,
                "titre": f"Communs — {c.domaine}",
            },
            session=session,
        )
        c.status = "promoted"
        session.add(
            CommonsAudit(
                content_hash=c.content_hash,
                target=TARGET_RAG,
                domaine=c.domaine,
                source_uri=source_uri,
                validated_by=c.validated_by,
            )
        )
        promus += 1

    await session.flush()
    return {"valides": len(cands), "promus": promus, "cible": TARGET_RAG}
