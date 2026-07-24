"""Hook `evidence` du RAGAgent : injecter des faits calculés dans le prompt.

Doctrine « le moteur calcule, le LLM narre » — un overlay peut fournir des
résultats déterministes que l'agent restitue sans les recalculer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from zolaos.agents.rag_agent import Match, RAGAgent
from zolaos.core.settings import Settings


class _Agent(RAGAgent):
    name = "test.evidence"
    rag_schema = "rag_legal"
    prompt_file = "fintech/generique.md"  # prompt public quelconque
    default_tags = ()
    requires_citation = False
    min_confidence = None
    response_schema = None
    top_k = 3


def _match() -> Match:
    return Match(
        content="Texte de référence — article pertinent.",
        score=0.2,
        source_uri="https://officiel.example/ref.pdf",
        source_id="ref",
        chunk_index=0,
        tags=["country:cg"],
        extra_metadata={},
    )


def _user_msg(prepared) -> str:  # type: ignore[no-untyped-def]
    return next(m.content for m in prepared.messages if m.role == "user")


def test_evidence_injectee_dans_le_prompt() -> None:
    agent = _Agent(AsyncMock(), Settings())
    prepared = agent.assemble(
        "Quelle est la posture de sécurité ?",
        [_match()],
        evidence="AUDIT DE DURCISSEMENT — MFA admin non conforme (critical).",
    )
    msg = _user_msg(prepared)
    assert "audit déterministe" in msg  # l'en-tête du bloc de preuves
    assert "MFA admin non conforme" in msg
    assert "Quelle est la posture de sécurité ?" in msg


def test_sans_evidence_pas_de_bloc() -> None:
    agent = _Agent(AsyncMock(), Settings())
    prepared = agent.assemble("Question simple", [_match()])
    assert "audit déterministe" not in _user_msg(prepared)
