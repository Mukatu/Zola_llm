"""Dépendances FastAPI partagées."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from zolaos.agents.brigade import SimulatedAgent
from zolaos.agents.meta.planning import PlanningAgent
from zolaos.agents.router import Router
from zolaos.core.orchestrator import Orchestrator
from zolaos.core.settings import Settings, get_settings
from zolaos.llm.factory import make_core_client, make_router_client


@lru_cache(maxsize=1)
def _shared_clients() -> tuple[Settings, object, object]:
    settings = get_settings()
    router_client = make_router_client(settings)
    core_client = make_core_client(settings)
    return settings, router_client, core_client


def get_orchestrator(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Orchestrator:
    """Construit l'orchestrateur. Cache les clients pour réutiliser les connexions HTTP."""
    _, router_client, core_client = _shared_clients()
    return Orchestrator(
        router=Router(router_client, settings),  # type: ignore[arg-type]
        planning=PlanningAgent(core_client, settings),  # type: ignore[arg-type]
        brigade=SimulatedAgent(router_client, settings),  # type: ignore[arg-type]
        settings=settings,
    )
