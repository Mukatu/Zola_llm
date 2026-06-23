"""Recherche RAG : similarité cosine pgvector + filtre tags (RBAC).

Usage typique depuis un sous-agent :

    matches = await retrieve(
        query="posologie paracétamol enfant",
        schema="rag_health",
        required_tags=["country:cg"],
        k=5,
    )
    # matches[i].content, matches[i].score, matches[i].tags, matches[i].source_uri
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.db.models import RAG_MODELS
from zolaos.db.session import get_session_factory
from zolaos.rag.embeddings import EmbeddingService, get_embedding_service

_log = get_logger("zolaos.rag.retrieval")


@dataclass(frozen=True)
class Match:
    """Un résultat de recherche RAG."""

    content: str
    score: float  # distance cosine (plus petit = plus proche)
    source_uri: str
    source_id: str | None
    chunk_index: int
    tags: list[str]
    extra_metadata: dict[str, Any]

    @property
    def similarity(self) -> float:
        """Conversion distance → similarité ∈ [0, 1] pour seuillage applicatif."""
        return max(0.0, 1.0 - self.score)


async def retrieve(
    *,
    query: str,
    schema: str,
    required_tags: list[str],
    k: int = 5,
    session: AsyncSession | None = None,
    embeddings: EmbeddingService | None = None,
) -> list[Match]:
    """Top-k voisins cosine filtrés par tags. RBAC : `required_tags` non vide.

    Lève ValueError si `required_tags` est vide (anti-leak strict, comme
    `MemoryAgent.recall` Phase 1).
    """
    if not required_tags:
        raise ValueError(
            "required_tags est obligatoire (RBAC anti-leak). " "Au minimum, passe `country:cg`."
        )
    if schema not in RAG_MODELS:
        raise ValueError(f"Schéma RAG inconnu: {schema!r}. Connus: {list(RAG_MODELS)}")
    model = RAG_MODELS[schema]
    embeddings = embeddings or get_embedding_service()

    qvec = await embeddings.aencode_one(query)

    # pgvector : `<=>` = cosine distance. ARRAY @> exige tous les tags requis.
    stmt = (
        select(
            model.content,
            (model.embedding.cosine_distance(qvec)).label("score"),
            model.source_uri,
            model.source_id,
            model.chunk_index,
            model.tags,
            model.extra_metadata,
        )
        .where(model.tags.contains(required_tags))
        .order_by("score")
        .limit(k)
    )

    if session is not None:
        rows = (await session.execute(stmt)).all()
    else:
        factory = get_session_factory()
        async with factory() as new_session:
            rows = (await new_session.execute(stmt)).all()

    matches = [
        Match(
            content=r.content,
            score=float(r.score),
            source_uri=r.source_uri,
            source_id=r.source_id,
            chunk_index=r.chunk_index,
            tags=list(r.tags),
            extra_metadata=dict(r.extra_metadata or {}),
        )
        for r in rows
    ]
    _log.info(
        "rag.retrieve",
        schema=schema,
        query_len=len(query),
        required_tags=required_tags,
        k=k,
        returned=len(matches),
        best_similarity=matches[0].similarity if matches else None,
    )
    return matches
