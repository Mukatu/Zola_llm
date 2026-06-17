"""Tests Phase 4 : sous-agents admin CG, reporting bailleurs, projets ONG.

Smoke test : instanciation + chargement de prompt + propagation tags +
intégration `RAG_MODELS` (ces agents utilisent `rag_legal` en placeholder
tant que `rag_grc` / `rag_erp` n'existent pas dans Phase 4).
"""

from __future__ import annotations

import pytest

from zolaos.agents.erp.projets_ong import ProjetsOngAgent
from zolaos.agents.grc.reporting_bailleurs import ReportingBailleursAgent
from zolaos.agents.legal.admin_cg import AdminCgAgent
from zolaos.agents.rag_agent import RAGAgent
from zolaos.core.settings import Settings
from zolaos.llm.factory import make_router_client

PHASE4_AGENTS = [AdminCgAgent, ReportingBailleursAgent, ProjetsOngAgent]


@pytest.fixture
def settings() -> Settings:
    return Settings()


# Marqueurs métier attendus dans le prompt de chaque sous-agent (au lieu de
# chercher le préfixe technique du pôle, qui ne figure pas dans le prompt
# rédigé en termes "humains" pour le LLM).
EXPECTED_PROMPT_MARKERS = {
    "legal.admin_cg": ("marchés publics", "armp", "cour des comptes"),
    "grc.reporting_bailleurs": ("bailleurs", "iati", "prag"),
    "erp.projets_ong": ("ong", "syscohada", "bailleur"),
}


@pytest.mark.parametrize("agent_cls", PHASE4_AGENTS)
def test_agent_instantiates_and_loads_prompt(agent_cls, settings) -> None:
    client = make_router_client(settings)
    try:
        agent = agent_cls(client=client, settings=settings)
        assert issubclass(agent_cls, RAGAgent), f"{agent_cls.__name__} doit hériter de RAGAgent"
        assert agent.name, f"{agent_cls.__name__} sans nom"
        assert agent.rag_schema in ("rag_legal", "rag_health"), (
            f"{agent_cls.__name__} doit utiliser un schéma RAG existant"
        )
        assert agent.prompt_file, f"{agent_cls.__name__} sans prompt_file"
        prompt = agent._system_prompt
        assert len(prompt) > 500, f"Prompt {agent.name} suspect trop court ({len(prompt)})"
        # Vérifie que le prompt couvre bien le périmètre métier annoncé
        markers = EXPECTED_PROMPT_MARKERS[agent.name]
        prompt_lower = prompt.lower()
        missing = [m for m in markers if m not in prompt_lower]
        assert not missing, (
            f"Prompt {agent.name} ne couvre pas tous les marqueurs métier attendus : "
            f"manquants={missing}"
        )
    finally:
        # client httpx — clean close
        import asyncio
        asyncio.run(client.aclose())


def test_admin_cg_has_political_sensitivity_marker(settings) -> None:
    """Vérifie que le prompt admin_cg contient les garde-fous neutralité politique."""
    client = make_router_client(settings)
    try:
        agent = AdminCgAgent(client=client, settings=settings)
        prompt = agent._system_prompt.lower()
        # Marqueurs de neutralité éditoriale exigés
        assert "neutralité" in prompt or "factuel" in prompt
        assert "qualification politique" in prompt or "politique" in prompt
        # Refus de l'attribution nominative
        assert "attribution personnelle" in prompt or "anonymise" in prompt or "anonymisé" in prompt or "anonymisée" in prompt
    finally:
        import asyncio
        asyncio.run(client.aclose())


def test_reporting_bailleurs_multilang_capability(settings) -> None:
    """Le prompt doit mentionner explicitement la capacité multi-langue FR/EN."""
    client = make_router_client(settings)
    try:
        agent = ReportingBailleursAgent(client=client, settings=settings)
        prompt = agent._system_prompt.lower()
        assert ("anglais" in prompt) or ("english" in prompt) or ("en " in prompt and "fr" in prompt)
        # Mentions des bailleurs principaux
        for bailleur in ("ue", "onu", "banque mondiale"):
            assert bailleur in prompt, f"bailleur '{bailleur}' non mentionné"
    finally:
        import asyncio
        asyncio.run(client.aclose())


def test_phase4_agents_count_matches_expectation() -> None:
    """Garde-fou : on s'attend à 3 sous-agents Phase 4 livrés."""
    assert len(PHASE4_AGENTS) == 3, "Phase 4 attendue : 3 sous-agents (admin CG, reporting bailleurs, projets ONG)"
