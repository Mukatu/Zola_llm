"""Tests du sous-agent RH (ERP §4.1).

- Smoke : instanciation, héritage RAGAgent, marqueurs métier du prompt.
- Fonctionnel : answer() en mode rédaction (RAG mocké) → citations ; garde-fou
  InsufficientContextError quand aucun match.
"""

from __future__ import annotations

import pytest

from zolaos.agents import rag_agent as rag_agent_mod
from zolaos.agents.erp.rh import RhAgent
from zolaos.agents.rag_agent import InsufficientContextError, RAGAgent
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient
from zolaos.rag.retrieval import Match


class _FakeClient(LLMClient):
    provider = "fake"

    def __init__(self, content: str) -> None:
        self._content = content

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        return GenerationResult(content=self._content, model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options

        async def _gen():
            yield self._content

        return _gen()

    async def health(self) -> bool:
        return True


@pytest.fixture
def settings() -> Settings:
    return Settings()


def _match(content: str, score: float = 0.1) -> Match:
    return Match(
        content=content,
        score=score,
        source_uri="code_travail_cg.pdf",
        source_id="Art.26",
        chunk_index=0,
        tags=["country:cg", "module:travail_cg"],
        extra_metadata={},
    )


def test_rh_agent_instantiates_and_prompt_markers(settings: Settings) -> None:
    agent = RhAgent(client=_FakeClient(""), settings=settings)
    assert issubclass(RhAgent, RAGAgent)
    assert agent.name == "erp.rh"
    assert agent.rag_schema == "rag_legal"
    prompt = agent._system_prompt.lower()
    assert len(prompt) > 500
    for marker in ("fiches de poste", "cdi", "cdd", "conformité", "code du travail", "jurisprudence"):
        assert marker in prompt, f"marqueur manquant: {marker}"
    # Assistance, pas substitution
    assert "juriste" in prompt or "avocat" in prompt


async def test_rh_agent_generates_with_citations(settings: Settings, monkeypatch) -> None:
    async def fake_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        assert schema == "rag_legal"
        assert "module:travail_cg" in required_tags
        return [_match("Art. 26 — mentions obligatoires du CDI."), _match("Période d'essai.", 0.2)]

    monkeypatch.setattr(rag_agent_mod, "retrieve", fake_retrieve)
    agent = RhAgent(client=_FakeClient("Projet de CDI conforme [1][2]."), settings=settings)
    resp = await agent.answer("Rédige un CDI pour un comptable, essai 3 mois.")
    assert resp.agent == "erp.rh"
    assert "CDI" in resp.content
    assert len(resp.citations) == 2
    assert resp.citations[0].source_id == "Art.26"


async def test_rh_agent_refuses_without_context(settings: Settings, monkeypatch) -> None:
    async def empty_retrieve(*, query, schema, required_tags, k):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(rag_agent_mod, "retrieve", empty_retrieve)
    agent = RhAgent(client=_FakeClient("ne devrait pas être appelé"), settings=settings)
    with pytest.raises(InsufficientContextError):
        await agent.answer("Rédige un contrat.")
