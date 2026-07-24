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
from zolaos.core import orchestrator as orch_mod
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient
from zolaos.rag.retrieval import Match

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
    """Aucun corpus nulle part : ni le retrieve des agents, ni le filet multi-schéma."""

    async def empty_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schema, required_tags, k
        return []

    async def empty_multi(*, query, schemas, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schemas, required_tags, k
        return {}

    monkeypatch.setattr(rag_agent_mod, "retrieve", empty_retrieve)
    monkeypatch.setattr(orch_mod, "retrieve_multi", empty_multi)


def _match(source_id: str, sim: float) -> Match:
    """Un match RAG factice de similarité `sim` (score = 1 - sim)."""
    return Match(
        content=f"Texte réglementaire {source_id} — article pertinent.",
        score=1.0 - sim,
        source_uri=f"https://officiel.example/{source_id}.pdf",
        source_id=source_id,
        chunk_index=0,
        tags=["country:cg"],
        extra_metadata={},
    )


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


async def test_general_pole_still_answers_without_corpus(settings: Settings, monkeypatch) -> None:
    """Pas d'agent RAG pour `general` → réponse libre légitime, pas d'abstention."""
    _empty_corpus(monkeypatch)
    decision = RouteDecision(pole=Pole.GENERAL, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Bonjour, peux-tu te présenter ?")

    assert "Je n'ai aucune source" not in result.responses[0].content
    # …mais la réponse est signalée comme non sourcée : le routeur a pu se tromper
    # de pôle, et une réponse libre ne doit jamais passer pour une réponse fiable.
    assert result.responses[0].grounding == "unsourced"


async def test_stream_path_applies_the_same_guardrail(settings: Settings, monkeypatch) -> None:
    """Le streaming ne doit pas être une porte dérobée contournant l'abstention."""
    _empty_corpus(monkeypatch)
    decision = RouteDecision(pole=Pole.FINTECH, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    text = "".join(
        [
            ev["text"]
            async for ev in orch.stream("Quel est le seuil de déclaration ?")
            if ev["type"] == "token"
        ]
    )

    assert "Je n'ai aucune source" in text
    assert _INVENTION not in text


async def test_safety_net_rescues_question_routed_to_pole_without_corpus(
    settings: Settings, monkeypatch
) -> None:
    """Question COBAC mal routée vers `grc` (sans agent RAG) : le filet la rattrape.

    Sans filet, elle tombait sur la brigade sans source alors que le règlement est
    dans rag_fintech. Le filet balaie les corpus publics et ancre la réponse.
    """

    # L'agent direct ne trouve rien (grc n'a de toute façon pas d'agent), mais le
    # balayage multi-schéma remonte un extrait solide dans rag_fintech.
    async def multi(*, query, schemas, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schemas, required_tags, k
        return {"rag_fintech": [_match("cemac_microfinance_2017", sim=0.62)]}

    monkeypatch.setattr(orch_mod, "retrieve_multi", multi)
    decision = RouteDecision(pole=Pole.GRC, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Comment la COBAC supervise-t-elle les EMF ?")

    resp = result.responses[0]
    assert resp.grounding == "sourced"
    assert resp.citations  # ancrée : au moins une citation
    assert resp.rag_schema == "rag_fintech"


async def test_safety_net_skips_general_pole(settings: Settings, monkeypatch) -> None:
    """`general` = le routeur juge la question NON métier → le filet ne s'exécute pas.

    Sinon un « bonjour » se ferait ancrer sur un texte de loi au hasard (bge-m3
    donne ~0,5 de similarité à tout texte français). On respecte ce jugement.
    """
    appele = {"multi": False}

    async def multi(*, query, schemas, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schemas, required_tags, k
        appele["multi"] = True
        return {"rag_legal": [_match("convention_mines", sim=0.6)]}

    monkeypatch.setattr(orch_mod, "retrieve_multi", multi)
    decision = RouteDecision(pole=Pole.GENERAL, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Bonjour, peux-tu te présenter ?")

    assert appele["multi"] is False  # le filet n'a pas tourné
    assert result.responses[0].grounding == "unsourced"


async def test_safety_net_gives_up_below_confidence(settings: Settings, monkeypatch) -> None:
    """Meilleur match trop faible → le filet renonce, on n'invente pas une source.

    Le seuil `min_confidence` de l'agent générique (0.5) tranche : un match à 0.3
    ne doit pas produire une réponse d'apparence sourcée.
    """

    async def multi(*, query, schemas, required_tags, k):  # type: ignore[no-untyped-def]
        _ = query, schemas, required_tags, k
        return {"rag_fintech": [_match("cemac_microfinance_2017", sim=0.3)]}

    monkeypatch.setattr(orch_mod, "retrieve_multi", multi)
    decision = RouteDecision(pole=Pole.GRC, module=None, confidence=0.9, complexity="simple")
    orch = _orchestrator(settings, decision, monkeypatch)

    result = await orch.handle("Question de gouvernance sans réponse dans le corpus")

    # grc n'est pas un pôle réglementé (pas d'agent) → repli brigade, unsourced.
    assert result.responses[0].grounding == "unsourced"
