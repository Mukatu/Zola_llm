"""Agent simulé de la brigade — Phase 1.

Sert à valider la traversée Router → Orchestrateur → Agent → Réponse de bout
en bout. Les vrais sous-agents (pharmacologie, OHADA, RH…) arrivent en
Phase 2-4.
"""

from __future__ import annotations

from dataclasses import dataclass

from zolaos.agents.router import Pole
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.brigade")


@dataclass(frozen=True)
class AgentResponse:
    pole: Pole
    content: str
    model: str
    duration_seconds: float


# Map pôle → libellé court pour le prompt système.
POLE_LABELS: dict[Pole, str] = {
    Pole.HEALTH: "Pharmacologie et santé (CIM-10 OMS et LNME congolaise)",
    Pole.LEGAL: "Droit (OHADA et droit national de la République du Congo)",
    Pole.ERP: "Gestion d'entreprise (RH, finance, comptabilité SYSCOHADA)",
    Pole.GRC: "Gouvernance, risque et conformité (réglementation congolaise et CEMAC)",
    Pole.FINTECH: "Fintech (scoring crédit, KYC, mobile money Congo)",
    Pole.CYBER: "Cybersécurité défensive",
    Pole.ENGINEERING: "Ingénierie logicielle",
    Pole.GENERAL: "Assistance générale",
}


class SimulatedAgent:
    """Agent placeholder. Répond via Llama-3-8B avec un prompt léger.

    Ne fait **pas** de RAG ni d'appel d'outils en Phase 1. Permet juste de
    valider la traversée et la latence p95.
    """

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def answer(self, pole: Pole, user_query: str) -> AgentResponse:
        label = POLE_LABELS.get(pole, "Assistance générale")
        system = (
            f"Tu es un sous-agent ZolaOS spécialisé en {label}. "
            "Tu réponds en français de manière concise (3 à 6 phrases), "
            "claire et orientée pour un utilisateur en République du Congo. "
            "Si une réponse exige des données précises (loi, posologie, montant) "
            "que tu n'as pas, tu le signales et tu demandes à être enrichi par RAG."
        )

        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=system),
                    Message(role="user", content=user_query),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.3, max_tokens=512),
            )
            outcome = "ok"
            return AgentResponse(
                pole=pole,
                content=result.content,
                model=result.model,
                duration_seconds=result.duration_seconds,
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=f"brigade.{pole.value}", outcome=outcome).inc()
