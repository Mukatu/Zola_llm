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

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings, get_settings
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
    # Score hybride (dense + lexical) ∈ [0, 1] attribué par `hybrid_rerank`.
    # None tant qu'aucun re-ranking n'a eu lieu. Plus grand = mieux. On NE touche
    # PAS à `score`/`similarity` (distance cosinus vraie) pour préserver les
    # garde-fous applicatifs (`min_confidence`) qui raisonnent sur la similarité.
    rerank_score: float | None = None

    @property
    def similarity(self) -> float:
        """Conversion distance → similarité ∈ [0, 1] pour seuillage applicatif."""
        return max(0.0, 1.0 - self.score)


# --------------------------------------------------------------------------- #
# Re-ranking hybride lexical déterministe (BM25-léger, SANS modèle → offline)  #
# --------------------------------------------------------------------------- #

# Mots vides français + bruit juridique/typographique fréquent. On les ignore
# côté requête ET côté chunk pour que seuls les termes de CONTENU pèsent.
_FRENCH_STOPWORDS: frozenset[str] = frozenset(
    {
        "au", "aux", "avec", "ce", "ces", "cet", "cette", "dans", "de", "des",
        "du", "elle", "en", "et", "eux", "il", "ils", "je", "la", "le", "les",
        "leur", "leurs", "lui", "ma", "mais", "me", "meme", "mes", "moi", "mon",
        "ne", "nos", "notre", "nous", "on", "ou", "par", "pas", "plus", "pour",
        "qu", "que", "quel", "quelle", "quelles", "quels", "qui", "sa", "se",
        "ses", "si", "son", "sont", "sur", "ta", "te", "tes", "toi", "ton", "tu",
        "un", "une", "vos", "votre", "vous", "y", "est", "etre", "ete", "avoir",
        "ont", "a", "as", "ai", "aux", "cela", "ceci", "comme", "donc", "car",
        "ni", "or", "dont", "les", "aussi", "tout", "tous", "toute", "toutes",
        "entre", "sous", "sans", "chez", "vers", "afin", "lors", "selon",
        # fragments d'élision fréquents une fois l'apostrophe tokenisée
        "d", "l", "j", "m", "n", "s", "t", "c", "qu",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _strip_accents(text: str) -> str:
    """« Préavis » → « preavis » : normalise pour un appariement robuste."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _content_terms(text: str) -> list[str]:
    """Termes de contenu significatifs : minuscule, sans accent, sans mots vides."""
    norm = _strip_accents(text.lower())
    return [
        tok
        for tok in _TOKEN_RE.findall(norm)
        if len(tok) >= 2 and tok not in _FRENCH_STOPWORDS
    ]


def hybrid_rerank(
    query: str,
    matches: list[Match],
    k: int,
    *,
    dense_weight: float = 0.5,
    lexical_weight: float = 0.5,
) -> list[Match]:
    """Re-classe un pool de candidats par score **hybride** dense + lexical.

    Motivation : le dense pur remonte des chunks sémantiquement proches mais qui
    ne régissent pas la question (l'exemple canonique : un article sur les
    *unions de syndicats* cité comme fondement du *préavis* de licenciement). Ici
    un chunk qui contient littéralement les termes décisifs de la requête
    (« préavis », « licenciement ») bat un chunk seulement proche sémantiquement.

    Mécanique (100% déterministe, aucune dépendance réseau/modèle) :
      1. Termes significatifs de la requête = tokens de contenu (accents/minuscule
         normalisés, mots vides FR retirés).
      2. Score lexical par candidat = BM25-léger sur ces termes, avec IDF calculé
         sur le pool lui-même (un terme rare dans le pool pèse plus) et une légère
         normalisation par longueur de chunk. Puis normalisé ∈ [0, 1] par le max
         du pool.
      3. Score dense = similarité cosinus (1 − distance) ∈ [0, 1].
      4. Score hybride = dense_weight*dense + lexical_weight*lexical.
      5. Tri décroissant, top-k. `rerank_score` porte le score hybride.

    Dégradation propre : requête sans terme de contenu, ou lexical désactivé
    (poids ≤ 0), ou aucun terme retrouvé → on retombe sur l'ordre dense.
    """
    if not matches:
        return []

    qterms = list(dict.fromkeys(_content_terms(query)))  # uniques, ordre stable
    if not qterms or lexical_weight <= 0:
        ordered = sorted(matches, key=lambda m: m.score)  # distance min = mieux
        return [replace(m, rerank_score=m.similarity) for m in ordered[:k]]

    docs = [_content_terms(m.content) for m in matches]
    n = len(matches)

    # IDF (BM25) sur le pool, restreint aux termes de la requête.
    df: Counter[str] = Counter()
    for terms in docs:
        present = set(terms)
        for t in qterms:
            if t in present:
                df[t] += 1
    idf = {
        t: math.log(1.0 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in qterms
    }

    avgdl = (sum(len(d) for d in docs) / n) or 1.0
    k1, b = 1.5, 0.75

    raw_scores: list[float] = []
    for terms in docs:
        counts = Counter(terms)
        dl = len(terms) or 1
        s = 0.0
        for t in qterms:
            tf = counts.get(t, 0)
            if not tf:
                continue
            denom = tf + k1 * (1.0 - b + b * dl / avgdl)
            s += idf[t] * (tf * (k1 + 1.0)) / denom
        raw_scores.append(s)

    max_raw = max(raw_scores) if raw_scores else 0.0

    scored: list[tuple[float, Match]] = []
    for m, raw in zip(matches, raw_scores, strict=True):
        lex_norm = (raw / max_raw) if max_raw > 0 else 0.0
        hybrid = dense_weight * m.similarity + lexical_weight * lex_norm
        scored.append((hybrid, m))

    # Tri stable : hybride décroissant, puis distance croissante pour départager.
    scored.sort(key=lambda pair: (-pair[0], pair[1].score))
    return [replace(m, rerank_score=h) for h, m in scored[:k]]


def _pool_size(settings: Settings, k: int) -> int:
    """Taille du pool de candidats dense à re-ranger (> k)."""
    return max(settings.RAG_HYBRID_FETCH_MULTIPLIER * k, settings.RAG_HYBRID_FETCH_FLOOR)


def rerank_or_trim(
    query: str,
    matches: list[Match],
    k: int,
    settings: Settings | None = None,
) -> list[Match]:
    """Applique le re-ranking hybride si activé, sinon tronque à l'ordre dense.

    Point d'entrée unique utilisé partout où l'on doit passer d'un pool de
    candidats à un top-k : `retrieve`, `retrieve_multi`, et les fusions côté
    agent (union communs/tenant, mélange secteur).
    """
    settings = settings or get_settings()
    if settings.RAG_HYBRID_RERANK_ENABLED:
        return hybrid_rerank(
            query,
            matches,
            k,
            dense_weight=settings.RAG_HYBRID_DENSE_WEIGHT,
            lexical_weight=settings.RAG_HYBRID_LEXICAL_WEIGHT,
        )
    ordered = sorted(matches, key=lambda m: m.score)
    return ordered[:k]


async def retrieve(
    *,
    query: str,
    schema: str,
    required_tags: list[str],
    k: int = 5,
    session: AsyncSession | None = None,
    embeddings: EmbeddingService | None = None,
    hybrid: bool | None = None,
) -> list[Match]:
    """Top-k voisins filtrés par tags. RBAC : `required_tags` non vide.

    Par défaut (hybride activé dans les settings) : on récupère un pool de
    candidats plus large que `k` par similarité cosinus dense, puis on re-classe
    par score **hybride dense + lexical** (`hybrid_rerank`) avant de tronquer à
    `k`. Un chunk qui contient réellement les termes juridiques de la requête
    remonte ainsi devant un chunk seulement proche sémantiquement.

    `hybrid` force explicitement le comportement (utile en test) ; None = lit le
    flag `RAG_HYBRID_RERANK_ENABLED`. Signature rétro-compatible : les appelants
    existants n'ont rien à changer.

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
    settings = get_settings()
    use_hybrid = settings.RAG_HYBRID_RERANK_ENABLED if hybrid is None else hybrid
    fetch_k = _pool_size(settings, k) if use_hybrid else k

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
        .where(model.tags.op("@>")(required_tags))
        .order_by("score")
        .limit(fetch_k)
    )

    if session is not None:
        rows = (await session.execute(stmt)).all()
    else:
        factory = get_session_factory()
        async with factory() as new_session:
            rows = (await new_session.execute(stmt)).all()

    candidates = [
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
    if use_hybrid:
        matches = hybrid_rerank(
            query,
            candidates,
            k,
            dense_weight=settings.RAG_HYBRID_DENSE_WEIGHT,
            lexical_weight=settings.RAG_HYBRID_LEXICAL_WEIGHT,
        )
    else:
        matches = candidates[:k]
    _log.info(
        "rag.retrieve",
        schema=schema,
        query_len=len(query),
        required_tags=required_tags,
        k=k,
        hybrid=use_hybrid,
        pool=len(candidates),
        returned=len(matches),
        best_similarity=matches[0].similarity if matches else None,
        best_rerank=matches[0].rerank_score if matches else None,
    )
    return matches


async def retrieve_multi(
    *,
    query: str,
    schemas: list[str],
    required_tags: list[str],
    k: int = 6,
    session: AsyncSession | None = None,
    embeddings: EmbeddingService | None = None,
) -> dict[str, list[Match]]:
    """Top-k dans **plusieurs** schémas, en n'encodant la requête qu'UNE fois.

    Sert le filet de rattrapage de l'orchestrateur : quand le routeur envoie une
    requête vers un pôle sans corpus, on balaie les corpus réglementaires publics
    pour retrouver l'ancrage plutôt que de laisser le modèle répondre sans source.
    L'embedding domine le coût d'un retrieve ; le mutualiser rend le balayage de
    N schémas quasi gratuit (une requête pgvector chacun, quelques ms).

    Retourne {schéma: matches} pour les seuls schémas ayant au moins un résultat.
    """
    if not required_tags:
        raise ValueError("required_tags est obligatoire (RBAC anti-leak).")
    embeddings = embeddings or get_embedding_service()
    settings = get_settings()
    use_hybrid = settings.RAG_HYBRID_RERANK_ENABLED
    fetch_k = _pool_size(settings, k) if use_hybrid else k
    qvec = await embeddings.aencode_one(query)

    async def _run(sess: AsyncSession) -> dict[str, list[Match]]:
        out: dict[str, list[Match]] = {}
        for schema in schemas:
            if schema not in RAG_MODELS:
                raise ValueError(f"Schéma RAG inconnu: {schema!r}")
            model = RAG_MODELS[schema]
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
                .where(model.tags.op("@>")(required_tags))
                .order_by("score")
                .limit(fetch_k)
            )
            rows = (await sess.execute(stmt)).all()
            if rows:
                candidates = [
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
                out[schema] = rerank_or_trim(query, candidates, k, settings)
        return out

    if session is not None:
        found = await _run(session)
    else:
        factory = get_session_factory()
        async with factory() as new_session:
            found = await _run(new_session)

    _log.info(
        "rag.retrieve_multi",
        schemas=schemas,
        query_len=len(query),
        hits={s: len(m) for s, m in found.items()},
        best={s: round(m[0].similarity, 3) for s, m in found.items()},
    )
    return found
