"""Tests du re-ranking hybride dense + lexical (`zolaos.rag.retrieval`).

Objectif : prouver — sans DB, sans modèle, 100% déterministe (offline) — qu'un
chunk contenant RÉELLEMENT les termes juridiques de la requête (« préavis »,
« licenciement ») est reclassé DEVANT un chunk seulement proche sémantiquement
(le cas pathologique : un article sur les *unions de syndicats* que le dense pur
remonte comme fondement du préavis).
"""

from __future__ import annotations

import pytest

from zolaos.core.settings import Settings
from zolaos.rag.retrieval import (
    Match,
    _content_terms,
    _strip_accents,
    hybrid_rerank,
    rerank_or_trim,
)


def _match(content: str, score: float, chunk_index: int = 0) -> Match:
    """Fabrique un Match synthétique. `score` = distance cosine (petit = proche)."""
    return Match(
        content=content,
        score=score,
        source_uri=f"mem://chunk/{chunk_index}",
        source_id=f"c{chunk_index}",
        chunk_index=chunk_index,
        tags=["country:cg"],
        extra_metadata={},
    )


# Le chunk pathologique : très proche sémantiquement (distance minuscule) mais
# ne contient AUCUN des termes décisifs de la question.
_SYNDICATS = _match(
    "Les unions de syndicats professionnels peuvent se constituer librement "
    "entre organisations de travailleurs relevant de branches connexes.",
    score=0.05,  # similarité 0.95 : le dense pur le classe premier
    chunk_index=1,
)

# Le chunk qui RÉGIT la question : moins proche sémantiquement, mais contient
# littéralement les termes juridiques décisifs.
_PREAVIS = _match(
    "En cas de licenciement, l'employeur est tenu de respecter un délai de "
    "préavis dont la durée dépend de l'ancienneté du salarié.",
    score=0.35,  # similarité 0.65 : le dense pur le classe second
    chunk_index=2,
)

_QUERY = "licenciement préavis dans le secteur bancaire"


def test_dense_only_ranks_wrong_chunk_first() -> None:
    """Contrôle : à l'ordre dense pur, le mauvais chunk (syndicats) est premier."""
    dense_order = sorted([_SYNDICATS, _PREAVIS], key=lambda m: m.score)
    assert dense_order[0] is _SYNDICATS  # le dense se trompe — c'est le problème


def test_hybrid_promotes_lexically_matching_chunk() -> None:
    """Le chunk contenant « préavis »/« licenciement » remonte DEVANT le dense-proche."""
    ranked = hybrid_rerank(_QUERY, [_SYNDICATS, _PREAVIS], k=2)
    assert ranked[0].chunk_index == _PREAVIS.chunk_index
    assert ranked[1].chunk_index == _SYNDICATS.chunk_index
    # rerank_score est renseigné et ordonné (plus grand = mieux).
    assert ranked[0].rerank_score is not None
    assert ranked[0].rerank_score > ranked[1].rerank_score  # type: ignore[operator]


def test_hybrid_preserves_true_similarity() -> None:
    """Le re-ranking NE touche PAS à score/similarity (garde-fou min_confidence)."""
    ranked = hybrid_rerank(_QUERY, [_SYNDICATS, _PREAVIS], k=2)
    promoted = next(m for m in ranked if m.chunk_index == _PREAVIS.chunk_index)
    assert promoted.score == pytest.approx(0.35)
    assert promoted.similarity == pytest.approx(0.65)


def test_lexical_weight_zero_falls_back_to_dense() -> None:
    """Poids lexical nul → on retombe strictement sur l'ordre dense."""
    ranked = hybrid_rerank(
        _QUERY, [_SYNDICATS, _PREAVIS], k=2, dense_weight=1.0, lexical_weight=0.0
    )
    assert ranked[0].chunk_index == _SYNDICATS.chunk_index


def test_query_without_content_terms_falls_back_to_dense() -> None:
    """Requête faite QUE de mots vides → aucun signal lexical → ordre dense."""
    ranked = hybrid_rerank("le la les de des", [_SYNDICATS, _PREAVIS], k=2)
    assert ranked[0].chunk_index == _SYNDICATS.chunk_index


def test_accent_insensitive_matching() -> None:
    """« préavis » (requête) matche « preavis » (chunk) et inversement."""
    accented = _match("Le PRÉAVIS de licenciement est obligatoire.", score=0.4, chunk_index=3)
    plain = _match("Dispositions générales sans rapport direct.", score=0.1, chunk_index=4)
    ranked = hybrid_rerank("preavis licenciement", [plain, accented], k=2)
    assert ranked[0].chunk_index == accented.chunk_index


def test_rare_pool_term_gets_idf_boost() -> None:
    """IDF sur le pool : un terme rare (préavis, présent 1 fois) pèse plus qu'un
    terme banal présent partout."""
    # « travail » apparaît dans les 3 → IDF faible ; « préavis » dans 1 → IDF fort.
    a = _match("contrat de travail et conditions de travail", score=0.10, chunk_index=5)
    b = _match("droit du travail et relations de travail", score=0.11, chunk_index=6)
    c = _match("le préavis en droit du travail", score=0.30, chunk_index=7)
    ranked = hybrid_rerank("travail préavis", [a, b, c], k=3)
    assert ranked[0].chunk_index == c.chunk_index  # le porteur du terme rare gagne


def test_empty_matches_returns_empty() -> None:
    assert hybrid_rerank(_QUERY, [], k=5) == []


def test_topk_truncation() -> None:
    pool = [_match(f"texte neutre numero {i}", score=0.1 * i, chunk_index=i) for i in range(6)]
    ranked = hybrid_rerank("terme absent xyz", pool, k=3)
    assert len(ranked) == 3


def test_rerank_or_trim_respects_settings_flag() -> None:
    """rerank_or_trim : activé → re-ranking ; désactivé → tri distance pur."""
    on = Settings(
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
        RAG_HYBRID_RERANK_ENABLED=True,
    )
    off = Settings(
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
        RAG_HYBRID_RERANK_ENABLED=False,
    )
    ranked_on = rerank_or_trim(_QUERY, [_SYNDICATS, _PREAVIS], k=2, settings=on)
    ranked_off = rerank_or_trim(_QUERY, [_SYNDICATS, _PREAVIS], k=2, settings=off)
    assert ranked_on[0].chunk_index == _PREAVIS.chunk_index  # hybride
    assert ranked_off[0].chunk_index == _SYNDICATS.chunk_index  # dense pur


def test_helpers_normalization() -> None:
    assert _strip_accents("Préavis Licénciement") == "Preavis Licenciement"
    terms = _content_terms("Le préavis de licenciement dans le secteur")
    assert "preavis" in terms
    assert "licenciement" in terms
    assert "le" not in terms  # mot vide retiré
    assert "de" not in terms
