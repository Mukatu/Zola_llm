"""Orchestrateur ZolaOS — pipeline Router → (Planning) → Agent(s) → réponse fusionnée.

Phase 1 : pipeline minimal mais complet, sans RAG (arrive en Phase 2).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from zolaos.agents.brigade import AgentResponse, SimulatedAgent
from zolaos.agents.meta.planning import Plan, PlanningAgent
from zolaos.agents.rag_agent import InsufficientContextError
from zolaos.agents.registry import default_rag_agent_for, rag_agent_for
from zolaos.agents.router import Pole, RouteDecision, Router
from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings

_log = get_logger("zolaos.core.orchestrator")


@dataclass(frozen=True)
class OrchestrationResult:
    request_id: uuid.UUID
    decision: RouteDecision
    plan: Plan | None
    responses: list[AgentResponse]
    duration_seconds: float


class Orchestrator:
    """Compose les méta-agents et la brigade pour servir une requête utilisateur."""

    def __init__(
        self,
        router: Router,
        planning: PlanningAgent,
        brigade: SimulatedAgent,
        settings: Settings,
    ) -> None:
        self._router = router
        self._planning = planning
        self._brigade = brigade
        self._settings = settings

    async def handle(
        self,
        user_query: str,
        *,
        request_id: uuid.UUID | None = None,
        tenant_id: str = "local",
    ) -> OrchestrationResult:
        request_id = request_id or uuid.uuid4()
        start = time.perf_counter()

        # Étape 1 : routage
        decision = await self._router.classify(user_query)

        # Étape 2 : planification si complexité ≠ simple
        plan: Plan | None = None
        if decision.complexity == "complex":
            plan = await self._planning.plan(user_query)
            if not plan.needs_planning:
                plan = None

        # Étape 3 : invocation de l'agent.
        # Si un agent RAG existe pour le module (droit, compta, santé…), on l'utilise :
        # il ancre sa réponse sur le corpus (retrieval + citations). Sinon — ou si le
        # corpus ne contient pas de quoi répondre (InsufficientContextError) — on
        # retombe sur l'agent générique.
        responses = [await self._answer(decision, user_query, tenant_id)]

        duration = time.perf_counter() - start
        _log.info(
            "orchestrator.handle",
            request_id=str(request_id),
            pole=decision.pole,
            complexity=decision.complexity,
            had_plan=plan is not None,
            duration_seconds=duration,
        )

        return OrchestrationResult(
            request_id=request_id,
            decision=decision,
            plan=plan,
            responses=responses,
            duration_seconds=duration,
        )

    async def _answer(
        self, decision: RouteDecision, user_query: str, tenant_id: str = "local"
    ) -> AgentResponse:
        """Répond via l'agent RAG du module, ou l'agent générique en repli.

        `tenant_id` : transmis à l'agent RAG pour fusionner le corpus de référence
        avec les documents téléversés par le client (« la loi + VOS règles »).
        """
        # Agent du module précis, sinon filet structurel : agent générique du pôle
        # (tout le corpus du pôle). Sinon seulement, agent placeholder.
        agent_cls = rag_agent_for(decision.module) or default_rag_agent_for(decision.pole)
        if agent_cls is not None:
            try:
                agent = agent_cls(self._brigade.client, self._settings, tenant_id=tenant_id)
                rr = await agent.answer(user_query)
                return AgentResponse(
                    pole=decision.pole,
                    content=rr.content,
                    model=self._settings.LLM_MODEL_BRIGADE,
                    duration_seconds=rr.duration_seconds,
                    citations=tuple(rr.citations),
                    rag_schema=agent.rag_schema,
                )
            except InsufficientContextError:
                _log.info(
                    "orchestrator.rag_fallback", pole=decision.pole.value, module=decision.module
                )
        return await self._brigade.answer(decision.pole, user_query)

    # Helper de construction par défaut.
    @classmethod
    def from_clients(
        cls,
        *,
        router_client,  # type: ignore[no-untyped-def]
        core_client,  # type: ignore[no-untyped-def]
        settings: Settings,
    ) -> Orchestrator:
        return cls(
            router=Router(router_client, settings),
            planning=PlanningAgent(core_client, settings),
            brigade=SimulatedAgent(router_client, settings),
            settings=settings,
        )


__all__ = ["Orchestrator", "OrchestrationResult", "Pole"]
