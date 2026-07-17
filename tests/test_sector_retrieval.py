"""Retrieve boosté par secteur — la bonne convention collective, pas un mélange.

Une question de droit du travail qui nomme un secteur (« licenciement dans le
secteur bancaire ») doit s'ancrer sur la convention DE CE secteur + le droit
commun, en écartant les conventions des AUTRES secteurs (qui se ressemblent
sémantiquement et polluaient les citations).
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.legal.travail_cg import TravailCgAgent
from zolaos.agents.rag_agent import RAGAgent
from zolaos.core.settings import Settings
from zolaos.llm.base import LLMClient
from zolaos.rag.retrieval import Match
from zolaos.rag.sectors import detect_sector

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


def _m(source_id: str, sim: float, *sector_tags: str) -> Match:
    return Match(
        content=f"{source_id} — extrait.",
        score=1.0 - sim,
        source_uri=f"u://{source_id}",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg", "module:travail_cg", *sector_tags],
        extra_metadata={},
    )


def test_detect_sector_hits_and_misses() -> None:
    assert detect_sector("Licenciement dans le secteur bancaire") == "banque"
    assert detect_sector("congés dans le secteur minier") == "mines"
    assert detect_sector("préavis en hôtellerie") == "hotellerie"
    # Ne doit PAS matcher : question générique, ou secteur financier (fintech).
    assert detect_sector("Quel est le délai de préavis ?") is None
    assert detect_sector("Comment la COBAC supervise les EMF ?") is None


async def test_sector_boost_keeps_right_convention_drops_others(
    settings: Settings, monkeypatch
) -> None:
    """Boost banque : convention_banques + code commun, PAS les autres secteurs."""

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        if "secteur:banque" in required_tags:
            # retrieve scopé : uniquement la convention du secteur.
            return [_m("convention_banques", 0.70, "secteur:banque")]
        # retrieve général : convention du secteur + AUTRES secteurs + droit commun.
        return [
            _m("convention_industrie", 0.68, "secteur:industrie"),
            _m("convention_banques", 0.66, "secteur:banque"),
            _m("code_travail_cg", 0.60),  # droit commun, sans tag secteur
            _m("convention_mines", 0.58, "secteur:mines"),
        ]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = TravailCgAgent(client=_DummyClient(), settings=settings)

    matches = await agent._primary_retrieve(
        query="Licenciement dans le secteur bancaire",
        tags=["country:cg", "module:travail_cg"],
        k=6,
    )

    ids = {m.source_id for m in matches}
    assert "convention_banques" in ids  # la bonne convention est là
    assert "code_travail_cg" in ids  # le droit commun aussi
    assert "convention_industrie" not in ids  # bruit d'autres secteurs écarté
    assert "convention_mines" not in ids


async def test_no_sector_falls_back_to_plain_retrieve(
    settings: Settings, monkeypatch
) -> None:
    """Sans secteur nommé : un seul retrieve, aucune double détente."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        calls.append(required_tags)
        return [_m("code_travail_cg", 0.6)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = TravailCgAgent(client=_DummyClient(), settings=settings)

    await agent._primary_retrieve(
        query="Quel est le délai de préavis de licenciement ?",
        tags=["country:cg", "module:travail_cg"],
        k=6,
    )

    # Un seul appel, sans tag secteur.
    assert len(calls) == 1
    assert not any(t.startswith("secteur:") for t in calls[0])


async def test_non_sector_aware_agent_ignores_sectors(
    settings: Settings, monkeypatch
) -> None:
    """Un agent non `sector_aware` ne déclenche jamais le boost, même si un
    secteur est nommé (ex. « bancaire » dans une question fintech)."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        calls.append(required_tags)
        return [_m("x", 0.6)]

    class _Plain(RAGAgent):
        name = "test.plain"
        rag_schema = "rag_fintech"
        prompt_file = "fintech/generique.md"
        default_tags = ("country:cg",)
        sector_aware = False

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = _Plain(client=_DummyClient(), settings=settings)

    await agent._primary_retrieve(
        query="supervision bancaire des EMF", tags=["country:cg"], k=6
    )

    assert len(calls) == 1  # pas de double détente
