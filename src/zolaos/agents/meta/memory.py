"""Méta-agent Mémoire — mémoire sémantique partagée via pgvector.

Filtrage RBAC par intersection de tags : une requête fournit l'ensemble des
tags qu'elle est autorisée à voir (`country:cg`, `tenant:X`, `health`…), et la
recherche est restreinte à ce périmètre.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.core.metrics import RAG_QUERIES_TOTAL
from zolaos.db.models import MemoryEntry
from zolaos.rag.embeddings import EmbeddingService

_log = get_logger("zolaos.agents.meta.memory")


@dataclass(frozen=True)
class MemoryHit:
    """Résultat d'une recherche mémoire."""

    id: uuid.UUID
    content: str
    score: float  # 1 - cosine_distance (plus haut = plus proche)
    tags: list[str]
    source: str | None
    extra_metadata: dict[str, Any]


class MemoryAgent:
    """Méta-agent Mémoire.

    - `remember()` : insère un fait avec ses tags d'accès.
    - `recall()` : recherche les top-k entrées sémantiquement proches, filtrées par tags.
    """

    def __init__(self, embeddings: EmbeddingService, default_country: str = "cg") -> None:
        self._embeddings = embeddings
        self._default_country = default_country

    async def remember(
        self,
        session: AsyncSession,
        *,
        content: str,
        tags: list[str] | None = None,
        source: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> uuid.UUID:
        """Insère un fait en mémoire."""
        all_tags = list({*(tags or []), f"country:{self._default_country}"})
        embedding = self._embeddings.encode_one(content)

        entry = MemoryEntry(
            content=content,
            embedding=embedding,
            tags=all_tags,
            source=source,
            extra_metadata=extra_metadata or {},
            expires_at=(
                datetime.utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None
            ),
        )
        session.add(entry)
        await session.flush()
        _log.info("memory.remember", entry_id=str(entry.id), tags=all_tags, source=source)
        return entry.id

    async def recall(
        self,
        session: AsyncSession,
        *,
        query: str,
        required_tags: list[str],
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[MemoryHit]:
        """Recherche top-k filtrée par tags (RBAC : tous les `required_tags` doivent matcher).

        Le score retourné est `1 - cosine_distance` ∈ [0, 1], 1 = identique.
        """
        if not required_tags:
            # Refus de recherche sans tag : prévient les fuites cross-tenant.
            raise ValueError("recall() exige au moins un tag de filtrage (RBAC).")

        embedding = self._embeddings.encode_one(query)

        # `@>` = "le tableau `tags` contient tous les éléments de `required_tags`"
        stmt = (
            select(
                MemoryEntry.id,
                MemoryEntry.content,
                MemoryEntry.tags,
                MemoryEntry.source,
                MemoryEntry.extra_metadata,
                (1 - MemoryEntry.embedding.cosine_distance(embedding)).label("score"),
            )
            .where(MemoryEntry.tags.op("@>")(required_tags))
            .where(
                (MemoryEntry.expires_at.is_(None))
                | (MemoryEntry.expires_at > text("now()"))
            )
            .order_by(MemoryEntry.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Métrique : compte par schéma (ici memory) et pays (premier tag country:*).
        country = next(
            (t.split(":", 1)[1] for t in required_tags if t.startswith("country:")),
            self._default_country,
        )
        RAG_QUERIES_TOTAL.labels(schema="memory", country=country).inc()

        hits = [
            MemoryHit(
                id=row.id,
                content=row.content,
                score=float(row.score),
                tags=list(row.tags),
                source=row.source,
                extra_metadata=dict(row.extra_metadata or {}),
            )
            for row in rows
            if float(row.score) >= min_score
        ]
        _log.info("memory.recall", k=len(hits), required_tags=required_tags)
        return hits
