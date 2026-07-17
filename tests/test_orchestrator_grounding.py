"""Garde-fou d'ancrage de l'orchestrateur — « pas de source, pas d'affirmation ».

Régression protégée : quand un pôle réglementé (droit, fintech, santé, ERP) a un
agent RAG mais que le corpus ne retourne rien, l'orchestrateur retombait sur la
brigade — un agent SANS aucune source. Le modèle inventait alors des règles
plausibles (textes de loi imaginaires, faux seuils). On refuse à la place.

Le repli brigade reste légitime pour les pôles sans agent RAG (assistance
générale) : aucune prétention réglementaire n'y est émise.
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.router import Pole, RouteDecision
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient

pytestmark = pytest.mark.asyncio

_INVENTION = "Selon le Code des Obligations d'Information et de Vigilance, l'EMF doit..."


class _FakeClient(LLMClient):
    """Modèle qui invente systématiquement — s'il est appelé, le garde-fou a cédé."""

    provider = "fake"

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        return GenerationResult(content=_INVENTION, model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        yield _INVENTION

    async def health(self) -> bool:
        return True


def _orchestrator(settings: Settings, decision: RouteDecision, monkeypatch) -> Orchestrator:
    orch = Orchestrator.from_clients(
        router_client=_FakeClient(),
        core_client=_FakeClient(),
        settings=settings,
    )

    async def fake_classify(_query: str) -> RouteDecision:
        return decision

    monkeypatch.setattr(orch._router, "classify", fake_classify)
    return orch


def _empty_corpus(monkeypatch) -> None:
    async def empty_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, required_tags, k
        return []

    monkeypatch.setattr(rag_agent_mod, "retrieve", empty_retrieve)


async def test_regulated_pole_without_corpus_refuses_instead_of_inventing(
    settings: Settings, monkeypatch
) -> None:
    _empty_corpus(monkeypatch)
    decision = RouteDecision(pole=Pole.LEGAL, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Quelles sont les obligations de vigilance pour un EMF ?")

    content = result.responses[0].content
    assert "Je n'ai aucune source" in content
    assert _INVENTION not in content  # le modèle n'a pas eu la parole
    assert result.responses[0].citations == ()
    assert result.responses[0].grounding == "abstained"


async def test_general_pole_still_answers_without_corpus(
    settings: Settings, monkeypatch
) -> None:
    """Pas d'agent RAG pour `general` → réponse libre légitime, pas d'abstention."""
    _empty_corpus(monkeypatch)
    decision = RouteDecision(pole=Pole.GENERAL, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Bonjour, peux-tu te présenter ?")

    assert "Je n'ai aucune source" not in result.responses[0].content
    # …mais la réponse est signalée comme non sourcée : le routeur a pu se tromper
    # de pôle, et une réponse libre ne doit jamais passer pour une réponse fiable.
    assert result.responses[0].grounding == "unsourced"


async def test_stream_path_applies_the_same_guardrail(
    settings: Settings, monkeypatch
) -> None:
    """Le streaming ne doit pas être une porte dérobée contournant l'abstention."""
    _empty_corpus(monkeypatch)
    decision = RouteDecision(pole=Pole.FINTECH, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    text = "".join(
        [ev["text"] async for ev in orch.stream("Quel est le seuil de déclaration ?") if ev["type"] == "token"]
    )

    assert "Je n'ai aucune source" in text
    assert _INVENTION not in text
