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

from zolaos.db.store_models import CommonsAudit, ContribCandidate, LearnedRule
from zolaos.rag.ingest import ingest_text
from zolaos.security.pii import PIIRedactionPolicy

TARGET_RAG = "rag_commons"
TARGET_RULES = "learned_rules"


def _document_text(cand: ContribCandidate) -> str:
    p = cand.payload or {}
    q = str(p.get("question", "")).strip()
    r = str(p.get("reponse", "")).strip()
    return f"Question : {q}\n\nRéponse : {r}"


async def _promote_learned_rule(session: AsyncSession, cand: ContribCandidate) -> None:
    """Upsert d'un mapping appris `(domaine, cle) -> valeur` (déterministe)."""
    p = cand.payload or {}
    cle = str(p.get("cle", "")).strip()
    valeur = str(p.get("valeur", "")).strip()
    if not cle or not valeur:
        return
    existing = (
        await session.execute(
            select(LearnedRule).where(LearnedRule.domaine == cand.domaine, LearnedRule.cle == cle)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            LearnedRule(
                domaine=cand.domaine,
                cle=cle,
                valeur=valeur,
                occurrences=cand.occurrences,
                validated_by=cand.validated_by,
            )
        )
    else:
        existing.valeur = valeur  # dernière validation fait foi
        existing.occurrences = max(existing.occurrences, cand.occurrences)
        existing.validated_by = cand.validated_by


async def promote_validated(session: AsyncSession, *, limit: int = 500) -> dict[str, Any]:
    """Ingère les candidats validés dans rag_commons + journalise (session migrator)."""
    cands = (
        (
            await session.execute(
                select(ContribCandidate).where(ContribCandidate.status == "validated").limit(limit)
            )
        )
        .scalars()
        .all()
    )

    vers_rag = 0
    vers_rules = 0
    for c in cands:
        # Candidats déterministes (mappings) → table de règles apprises, sans embeddings.
        if c.type == "categorisation":
            await _promote_learned_rule(session, c)
            c.status = "promoted"
            session.add(
                CommonsAudit(
                    content_hash=c.content_hash,
                    target=TARGET_RULES,
                    domaine=c.domaine,
                    validated_by=c.validated_by,
                )
            )
            vers_rules += 1
            continue

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
        vers_rag += 1

    await session.flush()
    return {
        "valides": len(cands),
        "promus": vers_rag + vers_rules,
        "rag_commons": vers_rag,
        "learned_rules": vers_rules,
    }
