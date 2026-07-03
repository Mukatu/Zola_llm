"""Brique 0 — l'orchestrateur route vers l'agent RAG (réponse ancrée + citations),
avec repli sur l'agent générique quand le corpus ne permet pas de répondre.
"""

from __future__ import annotations

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.brigade import SimulatedAgent
from zolaos.agents.registry import rag_agent_for
from zolaos.agents.router import Pole, RouteDecision
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.rag.retrieval import Match


class _FakeGen:
    def __init__(self, content: str) -> None:
        self.content = content
        self.model = "llama-3-8b"
        self.duration_seconds = 0.01


class _FakeClient:
    async def generate(self, messages, *, model, options):  # type: ignore[no-untyped-def]
        return _FakeGen("Réponse ancrée sur le corpus [1][2].")


class _FakeRouter:
    def __init__(self, decision: RouteDecision) -> None:
        self._d = decision

    async def classify(self, query: str) -> RouteDecision:
        return self._d


class _FakePlanning:
    async def plan(self, query: str):  # type: ignore[no-untyped-def]
        raise AssertionError("planning ne doit pas être appelé (complexity=simple)")


def _settings() -> Settings:
    return Settings(
        APP_ENV="dev",
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )


def _match(sid: str) -> Match:
    return Match(
        content=f"AUDCIF — Article {sid} — obligations comptables.",
        score=0.2,  # distance faible → similarité 0.8 (> min_confidence)
        source_uri=f"ohada://AUDCIF/article/{sid}",
        source_id=f"AUDCIF-art-{sid}",
        chunk_index=0,
        tags=["country:cg", "module:audcif"],
        extra_metadata={},
    )


def _orch(decision: RouteDecision) -> Orchestrator:
    s = _settings()
    return Orchestrator(
        router=_FakeRouter(decision),  # type: ignore[arg-type]
        planning=_FakePlanning(),  # type: ignore[arg-type]
        brigade=SimulatedAgent(_FakeClient(), s),  # type: ignore[arg-type]
        settings=s,
    )


def test_rag_agent_for_mapping() -> None:
    from zolaos.agents.erp.compta import ComptaAgent

    assert rag_agent_for("compta") is ComptaAgent
    assert rag_agent_for("ohada") is not None
    assert rag_agent_for(None) is None
    assert rag_agent_for("module_inexistant") is None


async def test_orchestrator_uses_rag_agent_and_returns_citations(monkeypatch) -> None:
    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        return [_match("3"), _match("17")]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)

    decision = RouteDecision(pole=Pole.ERP, module="compta", confidence=0.9, complexity="simple")
    result = await _orch(decision).handle("obligations de tenue de la comptabilité")

    resp = result.responses[0]
    assert resp.citations, "réponse RAG attendue avec citations"
    assert resp.citations[0].source_id == "AUDCIF-art-3"


async def test_orchestrator_falls_back_when_no_context(monkeypatch) -> None:
    async def empty_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(rag_agent_mod, "retrieve", empty_retrieve)

    decision = RouteDecision(pole=Pole.ERP, module="compta", confidence=0.9, complexity="simple")
    result = await _orch(decision).handle("question hors corpus")

    resp = result.responses[0]
    assert resp.citations == (), "repli générique → aucune citation"
    assert resp.content  # l'agent générique a bien répondu


async def test_orchestrator_generic_when_no_module(monkeypatch) -> None:
    # Un appel qui échouerait si un agent RAG était (à tort) sélectionné.
    def _boom(*a, **k):  # type: ignore[no-untyped-def]
        raise AssertionError("retrieve ne doit pas être appelé sans module")

    monkeypatch.setattr(rag_agent_mod, "retrieve", _boom)

    decision = RouteDecision(pole=Pole.GENERAL, module=None, confidence=0.5, complexity="simple")
    result = await _orch(decision).handle("bonjour")
    assert result.responses[0].citations == ()
