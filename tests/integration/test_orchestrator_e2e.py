"""Test d'intégration end-to-end : Router → Orchestrateur → Agent.

Marqué `integration` : exécuté manuellement ou en CI avec un serveur LLM
disponible (par défaut llama-server sur 11434, modèle 8B chargé en VRAM).

Cible Phase 1 : p95 < 2 s sur requête simple (sur GPU). En dev CPU only,
tolérance jusqu'à 90 s. Override via env LLM_E2E_LATENCY_SECONDS.

Lancement :
    pytest -m integration tests/integration/test_orchestrator_e2e.py
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from zolaos.agents.brigade import SimulatedAgent
from zolaos.agents.meta.planning import PlanningAgent
from zolaos.agents.router import Pole, Router
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings
from zolaos.llm.factory import make_core_client, make_router_client

pytestmark = pytest.mark.integration

# Override via env pour adapter dev CPU vs GPU vs CI.
_LATENCY_THRESHOLD_SECONDS = float(os.environ.get("LLM_E2E_LATENCY_SECONDS", "90"))


def _server_reachable(host: str) -> bool:
    # llama-server expose /health, Ollama expose /api/tags. On essaie les deux.
    for path in ("/health", "/api/tags"):
        try:
            r = httpx.get(f"{host}{path}", timeout=3.0)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            continue
    return False


@pytest.fixture
def settings() -> Settings:
    return Settings(
        LLM_HOST_ROUTER=os.environ.get("LLM_HOST_ROUTER", "http://localhost:11434"),
        LLM_HOST_CORE=os.environ.get("LLM_HOST_CORE", "http://localhost:11435"),
    )


@pytest.fixture
async def orchestrator(settings: Settings):  # type: ignore[no-untyped-def]
    if not _server_reachable(settings.LLM_HOST_ROUTER):
        pytest.skip(f"Serveur LLM indisponible sur {settings.LLM_HOST_ROUTER}")
    router_client = make_router_client(settings)
    core_client = make_core_client(settings)
    try:
        yield Orchestrator(
            router=Router(router_client, settings),
            planning=PlanningAgent(core_client, settings),
            brigade=SimulatedAgent(router_client, settings),
            settings=settings,
        )
    finally:
        await router_client.aclose()  # type: ignore[attr-defined]
        if core_client is not router_client:
            await core_client.aclose()  # type: ignore[attr-defined]


async def test_simple_health_query_routes_to_health(orchestrator) -> None:  # type: ignore[no-untyped-def]
    # Warmup : charge le modèle en VRAM (premier appel = cold start).
    await orchestrator.handle("ping")

    start = time.perf_counter()
    result = await orchestrator.handle(
        "Quelle est la posologie du paracétamol pour un enfant de 6 ans à Brazzaville ?"
    )
    elapsed = time.perf_counter() - start

    assert result.decision.pole == Pole.HEALTH
    assert result.responses, "au moins une réponse"
    assert elapsed < _LATENCY_THRESHOLD_SECONDS, (
        f"Latence {elapsed:.2f}s > seuil {_LATENCY_THRESHOLD_SECONDS}s. "
        f"Override via env LLM_E2E_LATENCY_SECONDS (cible Phase 1 GPU : 2.0)."
    )


async def test_simple_legal_query_routes_to_legal(orchestrator) -> None:  # type: ignore[no-untyped-def]
    result = await orchestrator.handle(
        "Rédige les clauses essentielles d'un contrat de bail commercial OHADA."
    )
    assert result.decision.pole == Pole.LEGAL


async def test_simple_erp_query_routes_to_erp(orchestrator) -> None:  # type: ignore[no-untyped-def]
    result = await orchestrator.handle(
        "Comment passer une écriture de paie SYSCOHADA pour un salarié au Congo ?"
    )
    assert result.decision.pole in {Pole.ERP, Pole.LEGAL}  # frontière acceptable
