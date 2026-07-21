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
from zolaos.agents.rag_agent import InsufficientContextError, RAGAgent, RAGPrepared
from zolaos.agents.registry import (
    default_rag_agent_for,
    generic_agent_for_schema,
    home_schema_for,
    public_regulatory_schemas,
    rag_agent_for,
)
from zolaos.agents.router import Pole, RouteDecision, Router
from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings
from zolaos.core.smalltalk import smalltalk_reply
from zolaos.rag.retrieval import Match, retrieve_multi

_log = get_logger("zolaos.core.orchestrator")

# Barre de similarité de l'ÉTAGE 2 du filet de rattrapage (balayage inter-domaines,
# hors schéma maison du pôle routé). Nettement plus haute que le seuil maison de
# l'étage 1 (`min_confidence` = 0.5 des agents génériques). bge-m3 comprime les
# similarités (~0.5 pour tout texte français) : sans cette barre relevée, un match
# TANGENTIEL faible rattraperait à tort (ex. du droit des sociétés OHADA « sauvé »
# par de la LBC-FT CEMAC). Calibration sur le corpus CG (pays:cg), meilleure
# similarité par schéma :
#   - « statuts SARL OHADA » : rag_legal (maison) 0.56 / rag_fintech 0.56 /
#     rag_erp 0.49 / rag_health 0.51 — le cluster tangentiel plafonne à ~0.56 ;
#   - « taux de la TVA » (mal routé fintech) : rag_legal (fiscal) 0.69 — vraie
#     erreur de routage inter-domaines, match franc.
# 0.60 sépare proprement les deux : bloque tout ≤0.56, laisse passer 0.69. En deçà
# → abstention (comportement sûr, déjà géré en aval pour les pôles réglementés).
# Surchargeable par un réglage `RAG_SAFETY_NET_CROSS_DOMAIN_MIN_SIM` sur Settings
# s'il est ajouté ultérieurement (getattr avec repli sur cette constante).
_CROSS_DOMAIN_SAFETY_NET_BAR = 0.60


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
        core_client: object | None = None,
    ) -> None:
        self._router = router
        self._planning = planning
        self._brigade = brigade
        self._settings = settings
        # Client du modèle « lourd » (70B). Génération des cas COMPLEXES seulement
        # (routage + retrieve restent sur le 8B). None → pas de 70B sélectif : on
        # génère toujours sur le client/modèle 8B de l'agent (comportement d'origine).
        self._core_client = core_client

    def _gen_overrides(self, decision: RouteDecision, deep: bool = False) -> dict[str, object]:
        """Client+modèle de génération à surcharger → 70B, ou `{}` (8B par défaut).

        Le 70B (`LLM_MODEL_CORE`) est sollicité, si `core_client` est disponible :
          - `deep=True` : mode « réponse approfondie » demandé EXPLICITEMENT par
            l'utilisateur (bouton), quelle que soit la complexité estimée ;
          - OU `decision.complexity ∈ LLM_CORE_ON_COMPLEXITY` : déclenchement auto
            (défaut « complex », rare). Le routage + le retrieve restent sur le 8B.
        """
        if self._core_client is None:
            return {}
        levels = {
            lvl.strip()
            for lvl in self._settings.LLM_CORE_ON_COMPLEXITY.split(",")
            if lvl.strip()
        }
        if deep or decision.complexity in levels:
            return {"client": self._core_client, "model": self._settings.LLM_MODEL_CORE}
        return {}

    async def handle(
        self,
        user_query: str,
        *,
        request_id: uuid.UUID | None = None,
        tenant_id: str = "local",
        deep: bool = False,
    ) -> OrchestrationResult:
        request_id = request_id or uuid.uuid4()
        start = time.perf_counter()

        # Étape 0 : salutation / bavardage → réponse conversationnelle, sans RAG.
        if (reply := smalltalk_reply(user_query)) is not None:
            return OrchestrationResult(
                request_id=request_id,
                decision=RouteDecision(pole=Pole.GENERAL, confidence=1.0, complexity="simple"),
                plan=None,
                responses=[
                    AgentResponse(
                        pole=Pole.GENERAL,
                        content=reply,
                        model="conversational",
                        duration_seconds=0.0,
                        citations=(),
                        grounding="abstained",  # pas de badge « sans source » sur un bonjour
                    )
                ],
                duration_seconds=time.perf_counter() - start,
            )

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
        responses = [await self._answer(decision, user_query, tenant_id, deep=deep)]

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
        deep: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Même pipeline que `handle`, mais émis au fil de l'eau.

        Le routage doit aboutir avant qu'on sache quel agent parle : il n'est pas
        streamable. La génération de l'agent, elle, l'est — et c'est là que se
        trouvent les secondes que l'utilisateur subit. Les citations partent dès
        que le retrieve est fait, donc avant le premier token du modèle.
        """
        request_id = request_id or uuid.uuid4()
        start = time.perf_counter()

        # Étape 0 : salutation / bavardage → réponse conversationnelle immédiate.
        if (reply := smalltalk_reply(user_query)) is not None:
            yield {"type": "routing", "pole": Pole.GENERAL.value, "module": None, "complexity": "simple"}
            yield {"type": "token", "text": reply}
            yield {
                "type": "done",
                "request_id": str(request_id),
                "grounding": "abstained",
                "duration_seconds": time.perf_counter() - start,
            }
            return

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

        # Étape 3 : agent du pôle routé, sinon filet de rattrapage multi-schéma.
        agent, prepared, regulated = await self._resolve_agent(decision, user_query, tenant_id)
        grounding = (
            "sourced"
            if prepared is not None
            else ("abstained" if regulated else "unsourced")
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
                        "extrait": c.content,
                    }
                    for c in prepared.citations
                ],
            }
            async for chunk in agent.stream_prepared(prepared, **self._gen_overrides(decision, deep)):
                yield {"type": "token", "text": chunk}
        elif regulated:
            # Pôle à corpus, rien à citer même après le filet → abstention plutôt
            # que laisser le modèle inventer.
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

    async def _resolve_agent(
        self, decision: RouteDecision, user_query: str, tenant_id: str
    ) -> tuple[RAGAgent | None, RAGPrepared | None, bool]:
        """Choisit l'agent qui ancrera la réponse.

        Retourne ``(agent, prepared, regulated)`` :
        - ``agent``/``prepared`` non None → une réponse sourcée est possible ;
        - ``regulated`` = le routage visait un pôle doté d'un corpus. S'il n'y a
          finalement rien à citer, ``regulated`` tranche : abstention (pôle
          réglementé) vs réponse libre (assistance générale).

        Deux tentatives : (1) l'agent du pôle routé ; (2) si celui-ci n'ancre
        rien — pôle sans corpus, ou corpus muet sur la requête — un **filet** qui
        balaie les corpus réglementaires publics. Une erreur de routage (ex. une
        question COBAC envoyée vers `grc`, sans corpus) ne doit pas priver d'une
        réponse sourcée quand le texte existe ailleurs.
        """
        agent_cls = rag_agent_for(decision.module) or default_rag_agent_for(decision.pole)
        regulated = agent_cls is not None
        if agent_cls is not None:
            agent = agent_cls(self._brigade.client, self._settings, tenant_id=tenant_id)
            try:
                return agent, await agent.prepare(user_query), regulated
            except InsufficientContextError:
                _log.info(
                    "orchestrator.rag_fallback", pole=decision.pole.value, module=decision.module
                )

        # Filet UNIQUEMENT pour un pôle métier sans corpus (grc, cyber…). On
        # l'exclut pour `general` : c'est le pôle où le routeur juge explicitement
        # que la question n'est PAS métier. Y balayer les corpus ancrerait un
        # « bonjour » sur un texte de loi au hasard — bge-m3 donne ~0,5 de
        # similarité à n'importe quel texte français, un seuil ne les sépare pas.
        if decision.pole is Pole.GENERAL:
            return None, None, regulated

        net = await self._safety_net(user_query, tenant_id, decision.pole)
        if net is not None:
            agent, prepared = net
            _log.info(
                "orchestrator.safety_net_hit",
                routed_pole=decision.pole.value,
                rescued_schema=agent.rag_schema,
            )
            return agent, prepared, regulated
        return None, None, regulated

    async def _safety_net(
        self, user_query: str, tenant_id: str, routed_pole: Pole
    ) -> tuple[RAGAgent, RAGPrepared] | None:
        """Filet de rattrapage à DEUX ÉTAGES, sur le seul chemin d'erreur.

        Le filet ne tourne que quand l'agent du pôle routé n'a rien ancré. Une
        seule requête est encodée pour tous les schémas (`retrieve_multi`) : le
        coût est ~un embedding + N requêtes pgvector, négligeable.

        Le piège que ce filet doit éviter : bge-m3 comprime les similarités
        (~0.5 pour tout texte français), donc « prendre le meilleur schéma toutes
        similarités confondues » rattrape avec un corpus TANGENTIEL (ex. du droit
        des sociétés OHADA « sauvé » par de la LBC-FT CEMAC). Deux étages séparent
        le vrai rattrapage inter-domaines du faux :

        - **Étage 1 — domaine d'origine.** On balaie d'ABORD le seul schéma
          « maison » du pôle routé (`home_schema_for`), au seuil de confiance
          NORMAL de l'agent (`min_confidence`, appliqué par `assemble`). Si ça
          passe, on l'utilise : c'est le domaine attendu, il est prioritaire —
          même si un autre schéma affiche une similarité brute plus élevée.

        - **Étage 2 — inter-domaines, dernier recours.** SEULEMENT si l'étage 1
          échoue (pas de schéma maison, ou son corpus muet / sous le seuil), on
          balaie les AUTRES schémas, mais avec une BARRE PLUS HAUTE
          (`RAG_SAFETY_NET_CROSS_DOMAIN_MIN_SIM`, 0.60 par défaut vs 0.5 en
          étage 1). Ainsi un match tangentiel faible NE déclenche pas, tandis
          qu'une vraie erreur de routage inter-domaines à match fort (ex. TVA
          envoyée à tort vers fintech → corpus fiscal à ~0.69) rattrape.
        """
        found = await retrieve_multi(
            query=user_query,
            schemas=public_regulatory_schemas(),
            required_tags=["country:cg"],
            k=6,
        )
        if not found:
            return None

        # --- Étage 1 : domaine d'origine (seuil normal de l'agent). ---
        home = home_schema_for(routed_pole)
        if home is not None and home in found:
            hit = self._ground_on_schema(user_query, home, found[home], tenant_id)
            if hit is not None:
                _log.info(
                    "orchestrator.safety_net_stage1",
                    routed_pole=routed_pole.value,
                    schema=home,
                )
                return hit

        # --- Étage 2 : inter-domaines, dernier recours, barre relevée. ---
        others = {s: m for s, m in found.items() if s != home}
        if not others:
            return None
        best_schema = max(others, key=lambda s: max(m.similarity for m in others[s]))
        best_sim = max(m.similarity for m in others[best_schema])
        bar = getattr(
            self._settings,
            "RAG_SAFETY_NET_CROSS_DOMAIN_MIN_SIM",
            _CROSS_DOMAIN_SAFETY_NET_BAR,
        )
        if best_sim < bar:
            _log.info(
                "orchestrator.safety_net_stage2_blocked",
                routed_pole=routed_pole.value,
                best_schema=best_schema,
                best_similarity=round(best_sim, 3),
                bar=bar,
            )
            return None
        hit = self._ground_on_schema(user_query, best_schema, others[best_schema], tenant_id)
        if hit is not None:
            _log.info(
                "orchestrator.safety_net_stage2",
                routed_pole=routed_pole.value,
                schema=best_schema,
                best_similarity=round(best_sim, 3),
            )
        return hit

    def _ground_on_schema(
        self, user_query: str, schema: str, matches: list[Match], tenant_id: str
    ) -> tuple[RAGAgent, RAGPrepared] | None:
        """Ancre la réponse sur `schema` via son agent générique.

        Les garde-fous de l'agent (`requires_citation`, `min_confidence`) restent
        appliqués par `assemble` : un match trop faible lève
        `InsufficientContextError` et on renonce (l'appelant enchaîne l'étage
        suivant ou l'abstention).
        """
        agent_cls = generic_agent_for_schema(schema)
        if agent_cls is None:
            return None
        agent = agent_cls(self._brigade.client, self._settings, tenant_id=tenant_id)
        try:
            return agent, agent.assemble(user_query, matches)
        except InsufficientContextError:
            return None

    async def _answer(
        self, decision: RouteDecision, user_query: str, tenant_id: str = "local", deep: bool = False
    ) -> AgentResponse:
        """Répond via l'agent RAG du pôle, le filet de rattrapage, ou en repli.

        `tenant_id` : transmis à l'agent RAG pour fusionner le corpus de référence
        avec les documents téléversés par le client (« la loi + VOS règles »).
        """
        agent, prepared, regulated = await self._resolve_agent(decision, user_query, tenant_id)

        if agent is not None and prepared is not None:
            rr = await agent.answer_prepared(prepared, **self._gen_overrides(decision, deep))
            return AgentResponse(
                pole=decision.pole,
                content=rr.content,
                model=self._settings.LLM_MODEL_BRIGADE,
                duration_seconds=rr.duration_seconds,
                citations=tuple(rr.citations),
                rag_schema=agent.rag_schema,
                grounding="sourced",
            )
        if regulated:
            # Pôle à corpus, mais rien à citer même après le filet → on s'abstient
            # au lieu de laisser le modèle inventer une règle plausible.
            _log.info("orchestrator.rag_refusal", pole=decision.pole.value)
            return AgentResponse(
                pole=decision.pole,
                content=refusal_message(decision.pole),
                model=self._settings.LLM_MODEL_BRIGADE,
                duration_seconds=0.0,
                citations=(),
                grounding="abstained",
            )
        # Pôle sans corpus (assistance générale…) et rien trouvé ailleurs : pas de
        # prétention réglementaire, la réponse libre reste légitime (signalée unsourced).
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
            core_client=core_client,
        )


__all__ = ["Orchestrator", "OrchestrationResult", "Pole"]
