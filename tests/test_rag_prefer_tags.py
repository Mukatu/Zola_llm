"""Mécanisme GÉNÉRIQUE de préférence douce de tags (`RAGAgent.prefer_tags`).

`retrieve()` filtre `required_tags` en `@>` (ET strict, superset) : on ne peut
donc PAS ajouter un tag de préférence (ex. `lang:fr`) aux tags requis sans
risquer d'exclure tout un corpus qui ne le porte pas encore. La préférence est
donc un mécanisme à DEUX PASSES, opt-in via l'attribut de classe `prefer_tags`
(défaut vide = comportement actuel inchangé, une seule passe) :

  1. passe 1 : `required_tags = default_tags + prefer_tags` ;
  2. si la passe 1 rend MOINS de `top_k` résultats : passe 2 SANS `prefer_tags`
     pour compléter (backfill), les préférés en tête, sans doublon
     `(source_uri, chunk_index)`, tronqué à `top_k`.

Ce test est PUBLIC et ne doit importer AUCUN module `zolaos.agents.polaris.*`
(code privé Polaris, gitignored / dépôt séparé) : il exerce uniquement
`RAGAgent`, générique, avec un agent de test jetable.
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.rag_agent import RAGAgent
from zolaos.core.settings import Settings
from zolaos.llm.base import LLMClient
from zolaos.rag.retrieval import Match

pytestmark = pytest.mark.asyncio


class _DummyClient(LLMClient):
    provider = "fake"

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError
        yield ""

    async def health(self) -> bool:
        return True


def _m(source_id: str, sim: float, *tags: str) -> Match:
    return Match(
        content=f"{source_id} — extrait.",
        score=1.0 - sim,
        source_uri=f"u://{source_id}",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg", *tags],
        extra_metadata={},
    )


class _PlainAgent(RAGAgent):
    """Agent générique de test, `prefer_tags` vide (comportement actuel)."""

    name = "test.plain_no_pref"
    rag_schema = "rag_fintech"
    prompt_file = "fintech/generique.md"
    default_tags = ("country:cg",)


class _PreferFrAgent(RAGAgent):
    """Agent générique de test, `prefer_tags = ("lang:fr",)`."""

    name = "test.prefer_fr"
    rag_schema = "rag_fintech"
    prompt_file = "fintech/generique.md"
    default_tags = ("country:cg",)
    prefer_tags = ("lang:fr",)
    top_k = 3


async def test_no_prefer_tags_is_single_pass(settings: Settings, monkeypatch) -> None:
    """`prefer_tags` vide → EXACTEMENT le comportement actuel : un seul retrieve,
    aucun tag de préférence injecté, aucun surcoût."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        calls.append(list(required_tags))
        return [_m("a", 0.6)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _PlainAgent(client=_DummyClient(), settings=settings)

    matches = await agent._retrieve_preferred(query="q", tags=["country:cg"], k=3)

    assert len(calls) == 1
    assert calls[0] == ["country:cg"]
    assert [m.source_id for m in matches] == ["a"]


async def test_prefer_tags_first_pass_sufficient_no_backfill(
    settings: Settings, monkeypatch
) -> None:
    """Passe 1 rend déjà `k` résultats → PAS de passe 2 (pas de backfill)."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema
        calls.append(list(required_tags))
        if "lang:fr" in required_tags:
            return [_m("fr1", 0.9, "lang:fr"), _m("fr2", 0.8, "lang:fr"), _m("fr3", 0.7, "lang:fr")]
        raise AssertionError("la passe 2 ne doit pas être appelée si la passe 1 suffit")

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _PreferFrAgent(client=_DummyClient(), settings=settings)

    matches = await agent._retrieve_preferred(query="q", tags=["country:cg"], k=3)

    assert len(calls) == 1
    assert set(calls[0]) == {"country:cg", "lang:fr"}
    assert [m.source_id for m in matches] == ["fr1", "fr2", "fr3"]


async def test_prefer_tags_backfill_when_pass1_insufficient_no_duplicates(
    settings: Settings, monkeypatch
) -> None:
    """Passe 1 insuffisante (< k) → passe 2 backfill : préférés EN TÊTE,
    complément SANS DOUBLON, tronqué à k."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        calls.append(list(required_tags))
        if "lang:fr" in required_tags:
            # Passe 1 : un seul résultat FR, insuffisant pour k=3.
            return [_m("fr1", 0.9, "lang:fr")]
        # Passe 2 : le FR déjà vu ressort (même chunk) + deux nouveaux EN.
        return [
            _m("fr1", 0.9, "lang:fr"),
            _m("en1", 0.75),
            _m("en2", 0.65),
        ]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _PreferFrAgent(client=_DummyClient(), settings=settings)

    matches = await agent._retrieve_preferred(query="q", tags=["country:cg"], k=3)

    assert len(calls) == 2
    assert set(calls[0]) == {"country:cg", "lang:fr"}
    assert set(calls[1]) == {"country:cg"}
    ids = [m.source_id for m in matches]
    assert ids == ["fr1", "en1", "en2"]  # préféré en tête, pas de doublon fr1, tronqué à 3
    assert len(ids) == len(set(ids))


async def test_prefer_tags_backfill_truncates_to_top_k(settings: Settings, monkeypatch) -> None:
    """Le complément de la passe 2 est tronqué à `k`, jamais dépassé."""

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        if "lang:fr" in required_tags:
            return []
        return [_m("en1", 0.9), _m("en2", 0.8), _m("en3", 0.7), _m("en4", 0.6)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _PreferFrAgent(client=_DummyClient(), settings=settings)  # top_k = 3

    matches = await agent._retrieve_preferred(query="q", tags=["country:cg"], k=3)

    assert len(matches) == 3
    assert [m.source_id for m in matches] == ["en1", "en2", "en3"]


async def test_no_facet_primary_retrieve_uses_preference(settings: Settings, monkeypatch) -> None:
    """Intégration : `_primary_retrieve` (chemin sans facette) applique bien la
    préférence via `_retrieve_preferred`, sans rien changer pour un agent au
    `prefer_tags` vide."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, k
        calls.append(list(required_tags))
        return [_m("a", 0.6)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _PlainAgent(client=_DummyClient(), settings=settings)

    await agent._primary_retrieve(query="q", tags=["country:cg"], k=3)

    assert len(calls) == 1
    assert calls[0] == ["country:cg"]
