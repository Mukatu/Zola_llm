"""Orchestrateur ZolaOS — pipeline Router → (Planning) → Agent(s) → réponse fusionnée.

Phase 1 : pipeline minimal mais complet, sans RAG (arrive en Phase 2).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from zolaos.agents.brigade import POLE_LABELS, AgentResponse, SimulatedAgent
from zolaos.agents.meta.planning import Plan, PlanningAgent
from zolaos.agents.rag_agent import InsufficientContextError
from zolaos.agents.registry import default_rag_agent_for, rag_agent_for
from zolaos.agents.router import Pole, RouteDecision, Router
from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings

_log = get_logger("zolaos.core.orchestrator")


def refusal_message(pole: Pole) -> str:
    """Réponse quand le corpus d'un pôle réglementé n'a pas de quoi répondre.

    Ne jamais retomber sur un agent sans source dans ce cas : c'est exactement
    là que le modèle invente un texte de loi ou un seuil plausible. Mieux vaut
    une abstention utile qu'une règle fabriquée.
    """
    label = POLE_LABELS.get(pole, "ce domaine")
    return (
        f"Je n'ai aucune source dans ma documentation ({label}) permettant de traiter "
        "cette question.\n\n"
        "Je préfère m'abstenir plutôt que d'avancer une règle, un seuil ou une référence "
        "que je n'ai pas vérifiés. Ajoutez le texte de référence dans la Bibliothèque et "
        "je répondrai en le citant."
    )


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

    async def stream(
        self,
        user_query: str,
        *,
        request_id: uuid.UUID | None = None,
        tenant_id: str = "local",
    ) -> AsyncIterator[dict[str, Any]]:
        """Même pipeline que `handle`, mais émis au fil de l'eau.

        Le routage doit aboutir avant qu'on sache quel agent parle : il n'est pas
        streamable. La génération de l'agent, elle, l'est — et c'est là que se
        trouvent les secondes que l'utilisateur subit. Les citations partent dès
        que le retrieve est fait, donc avant le premier token du modèle.
        """
        request_id = request_id or uuid.uuid4()
        start = time.perf_counter()

        # Étape 1 : routage
        decision = await self._router.classify(user_query)
        yield {
            "type": "routing",
            "pole": decision.pole.value,
            "module": decision.module,
            "complexity": decision.complexity,
        }

        # Étape 2 : planification si complexité ≠ simple (parité avec `handle`)
        if decision.complexity == "complex":
            plan = await self._planning.plan(user_query)
            if plan.needs_planning:
                yield {
                    "type": "plan",
                    "rationale": plan.rationale,
                    "steps": [s.model_dump() for s in plan.steps],
                }

        # Étape 3 : agent RAG du module, sinon filet structurel du pôle.
        agent_cls = rag_agent_for(decision.module) or default_rag_agent_for(decision.pole)
        agent = None
        prepared = None
        if agent_cls is not None:
            agent = agent_cls(self._brigade.client, self._settings, tenant_id=tenant_id)
            try:
                prepared = await agent.prepare(user_query)
            except InsufficientContextError:
                _log.info(
                    "orchestrator.rag_fallback", pole=decision.pole.value, module=decision.module
                )
                prepared = None

        grounding = (
            "sourced"
            if prepared is not None
            else ("abstained" if agent_cls is not None else "unsourced")
        )

        if agent is not None and prepared is not None:
            yield {
                "type": "citations",
                "rag_schema": agent.rag_schema,
                "citations": [
                    {
                        "index": c.index,
                        "source_uri": c.source_uri,
                        "source_id": c.source_id,
                        "similarity": c.similarity,
                    }
                    for c in prepared.citations
                ],
            }
            async for chunk in agent.stream_prepared(prepared):
                yield {"type": "token", "text": chunk}
        elif agent_cls is not None:
            # Même garde-fou que `_answer` : le pôle a un corpus, il n'a rien donné
            # → on s'abstient au lieu de laisser le modèle inventer.
            yield {"type": "token", "text": refusal_message(decision.pole)}
        else:
            async for chunk in self._brigade.stream(decision.pole, user_query):
                yield {"type": "token", "text": chunk}

        duration = time.perf_counter() - start
        _log.info(
            "orchestrator.stream",
            request_id=str(request_id),
            pole=decision.pole,
            grounding=grounding,
            duration_seconds=duration,
        )
        yield {
            "type": "done",
            "request_id": str(request_id),
            "grounding": grounding,
            "duration_seconds": duration,
        }

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
            agent = agent_cls(self._brigade.client, self._settings, tenant_id=tenant_id)
            try:
                rr = await agent.answer(user_query)
                return AgentResponse(
                    pole=decision.pole,
                    content=rr.content,
                    model=self._settings.LLM_MODEL_BRIGADE,
                    duration_seconds=rr.duration_seconds,
                    citations=tuple(rr.citations),
                    rag_schema=agent.rag_schema,
                    grounding="sourced",
                )
            except InsufficientContextError:
                # Un agent RAG existait pour cette question : le pôle est censé être
                # couvert par un corpus, et ce corpus n'a rien. Retomber ici sur la
                # brigade (aucune source) revenait à laisser le modèle inventer une
                # règle plausible — on refuse à la place.
                _log.info(
                    "orchestrator.rag_refusal", pole=decision.pole.value, module=decision.module
                )
                return AgentResponse(
                    pole=decision.pole,
                    content=refusal_message(decision.pole),
                    model=self._settings.LLM_MODEL_BRIGADE,
                    duration_seconds=0.0,
                    citations=(),
                    rag_schema=agent.rag_schema,
                    grounding="abstained",
                )
        # Aucun agent RAG pour ce pôle (assistance générale, ingénierie…) : pas de
        # prétention réglementaire, la réponse libre reste légitime.
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
