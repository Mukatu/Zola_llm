"""Boost par forme juridique — la bonne société OHADA, pas un mélange.

Une question sur une SARL (Acte uniforme sociétés commerciales, AUSCGIE) ne doit
pas s'ancrer sur les articles des sociétés COOPÉRATIVES (AUSCOOP, autre acte, au
texte mieux océrisé qui ressortait à tort). Même mécanique que le boost secteur.
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.legal.ohada import OhadaAgent
from zolaos.core.settings import Settings
from zolaos.llm.base import LLMClient
from zolaos.rag.formes import detect_forme_juridique
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


def _m(source_id: str, sim: float, *forme_tags: str) -> Match:
    return Match(
        content=f"{source_id} — extrait.",
        score=1.0 - sim,
        source_uri=f"u://{source_id}",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg", "module:ohada", *forme_tags],
        extra_metadata={},
    )


def test_detect_forme_hits_and_misses() -> None:
    assert detect_forme_juridique("mentions des statuts d'une SARL") == "sarl"
    assert detect_forme_juridique("une société coopérative peut-elle...") == "cooperative"
    assert detect_forme_juridique("société en nom collectif") == "snc"
    # Ne doit PAS matcher : question générique sans forme nommée.
    assert detect_forme_juridique("mentions obligatoires des statuts") is None
    assert detect_forme_juridique("quel est le capital social minimum ?") is None


async def test_forme_boost_keeps_sarl_drops_cooperative(settings: Settings, monkeypatch) -> None:
    """Boost SARL : articles AUSCGIE SARL + droit commun, PAS les coopératives."""

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        if "forme:sarl" in required_tags:
            return [_m("AUSCGIE-art-310", 0.60, "forme:sarl")]
        # retrieve général : SARL + coopératives (OCR propre, sim plus haute) + commun.
        return [
            _m("AUSCOOP-art-68", 0.66, "forme:cooperative"),
            _m("AUSCGIE-art-13", 0.58, "forme:sarl"),
            _m("AUSCGIE-art-4", 0.55),  # disposition commune, sans tag forme
            _m("AUSCOOP-art-42", 0.54, "forme:cooperative"),
        ]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = OhadaAgent(client=_DummyClient(), settings=settings)

    matches = await agent._primary_retrieve(
        query="mentions obligatoires des statuts d'une SARL",
        tags=["country:cg", "module:ohada"],
        k=6,
    )

    ids = {m.source_id for m in matches}
    assert "AUSCGIE-art-310" in ids  # l'article SARL scopé est garanti présent
    assert "AUSCGIE-art-4" in ids  # disposition commune conservée
    assert "AUSCOOP-art-68" not in ids  # coopératives écartées malgré une sim plus haute
    assert "AUSCOOP-art-42" not in ids


async def test_no_forme_falls_back_to_plain_retrieve(settings: Settings, monkeypatch) -> None:
    """Sans forme nommée : un seul retrieve, aucune double détente."""
    calls: list[list[str]] = []

    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, k
        calls.append(required_tags)
        return [_m("AUSCGIE-art-1", 0.6)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = OhadaAgent(client=_DummyClient(), settings=settings)

    await agent._primary_retrieve(
        query="quel est le capital social minimum en droit OHADA ?",
        tags=["country:cg", "module:ohada"],
        k=6,
    )

    assert len(calls) == 1
    assert not any(t.startswith("forme:") for t in calls[0])
