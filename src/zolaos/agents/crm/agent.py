"""Agent Commercial / CRM — couche IA (addendum §3.2, CRM-2).

Délègue tout le **déterministe** au moteur (`engine.py`) — pipeline, scoring,
relances — et n'utilise le LLM que pour **rédiger** (emails de relance,
propositions commerciales) et **narrer/prioriser** (synthèse pipeline). Le LLM
ne calcule ni montant ni score. Disponible profils box et cortex.

Overlay Polaris correspondant : audit commercial/performance (dépôt privé).
"""

from __future__ import annotations

import time
from datetime import date

from zolaos.agents._prompts import load_prompt
from zolaos.agents.crm.engine import (
    LeadScore,
    LeadScoringWeights,
    PipelineStats,
    RelanceItem,
    detect_relances,
    pipeline_stats,
    score_lead,
)
from zolaos.agents.crm.models import Opportunity, Quote
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.crm.agent")


class CrmAgent:
    """Agent commercial : déterministe (engine) + rédaction/narration (LLM)."""

    name = "crm.commercial"
    prompt_file = "crm/commercial.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    # ----------------------------------------------------- déterministe

    def pipeline(self, opportunities: list[Opportunity]) -> PipelineStats:
        return pipeline_stats(opportunities)

    def prioritize_leads(
        self,
        opportunities: list[Opportunity],
        *,
        weights: LeadScoringWeights | None = None,
        as_of: date | None = None,
    ) -> list[tuple[Opportunity, LeadScore]]:
        """Score chaque opportunité et trie par score décroissant (déterministe)."""
        scored = [(o, score_lead(o, weights=weights, as_of=as_of)) for o in opportunities]
        return sorted(scored, key=lambda t: t[1].score, reverse=True)

    def relances(
        self, quotes: list[Quote], opportunities: list[Opportunity], *, as_of: date | None = None
    ) -> list[RelanceItem]:
        return detect_relances(quotes, opportunities, as_of=as_of)

    # ----------------------------------------------------- génératif (LLM)

    async def _generate(self, user_msg: str, op: str, *, max_tokens: int = 900) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("crm", "commercial.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.3, max_tokens=max_tokens),
            )
            outcome = "ok"
            _log.info("crm_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()

    async def draft_relance(self, item: RelanceItem, *, client_nom: str) -> str:
        """Rédige un email de relance à partir d'un item détecté (déterministe)."""
        user_msg = (
            f"Rédige un email de relance commercial, ton professionnel et courtois, en français.\n"
            f"Client : {client_nom}\n"
            f"Contexte (détecté automatiquement) : {item.libelle} (priorité {item.priorite}).\n"
            "Objet + corps concis. N'invente pas de montant non fourni."
        )
        return await self._generate(user_msg, "draft_relance")

    async def draft_proposition(self, *, client_nom: str, besoin: str, montant_xaf: str | None = None) -> str:
        """Rédige une proposition commerciale (génératif)."""
        montant = f"Budget indicatif : {montant_xaf} XAF.\n" if montant_xaf else ""
        user_msg = (
            f"Rédige une proposition commerciale structurée (français) pour le client {client_nom}.\n"
            f"Besoin exprimé : {besoin}\n{montant}"
            "Structure : contexte, solution proposée, bénéfices, prochaines étapes. "
            "N'invente pas de prix non fourni."
        )
        return await self._generate(user_msg, "draft_proposition", max_tokens=1200)

    @staticmethod
    def _format_pipeline(stats: PipelineStats, relances: list[RelanceItem] | None) -> str:
        lines = [
            "--- Pipeline (chiffres déjà calculés) ---",
            f"Opportunités ouvertes : {stats.nb_open}",
            f"Valeur totale ouverte : {stats.total_open_xaf} XAF",
            f"Valeur pondérée : {stats.weighted_open_xaf} XAF",
            f"Taux de conversion : {stats.win_rate_pct} %",
        ]
        for etape, montant in stats.par_etape_xaf.items():
            lines.append(f"- {etape} : {montant} XAF")
        if relances:
            lines.append(f"Relances à traiter : {len(relances)}")
            for r in relances:
                lines.append(f"- [{r.priorite}] {r.libelle}")
        return "\n".join(lines)

    async def synthesize_pipeline(
        self, stats: PipelineStats, *, relances: list[RelanceItem] | None = None
    ) -> str:
        """Synthèse commerciale narrative à partir du pipeline (le LLM ne recalcule pas)."""
        user_msg = (
            f"{self._format_pipeline(stats, relances)}\n\n"
            "Rédige une synthèse commerciale à partir de CES chiffres uniquement : état du "
            "pipeline, priorités, relances à mener. N'invente aucun chiffre."
        )
        return await self._generate(user_msg, "synthesize_pipeline")
