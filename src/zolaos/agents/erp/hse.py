"""Hygiène, Sécurité & Environnement / RSE — module ERP (OPS-5).

Indispensable pour télécom/industrie et exigé par les bailleurs (lien GRC).
**Déterministe d'abord** : suivi des incidents, cartographie des risques
(criticité = probabilité × gravité) et indicateurs HSE (taux de fréquence/
gravité) calculés **en code**. Le `HseAgent` **rédige** (plans de prévention,
rapports de durabilité).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.hse")

TypeIncident = Literal["accident_travail", "presque_accident", "environnemental", "maladie_pro", "autre"]
Gravite = Literal["mineur", "grave", "critique"]
Niveau = Literal["faible", "moyen", "eleve", "critique"]


# ============================================================ modèles

class Incident(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    date_incident: date
    type_incident: TypeIncident = "autre"
    gravite: Gravite = "mineur"
    description: str = ""
    jours_arret: int = Field(default=0, ge=0)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class Risque(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    libelle: str
    probabilite: int = Field(..., ge=1, le=5)
    gravite: int = Field(..., ge=1, le=5)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@dataclass(frozen=True)
class RisqueEvalue:
    reference: str
    libelle: str
    criticite: int            # 1..25
    niveau: Niveau


# ============================================================ moteur (pur)

def criticite(risque: Risque) -> int:
    return risque.probabilite * risque.gravite


def niveau_criticite(c: int) -> Niveau:
    if c <= 4:
        return "faible"
    if c <= 9:
        return "moyen"
    if c <= 15:
        return "eleve"
    return "critique"


def cartographie_risques(risques: list[Risque]) -> list[RisqueEvalue]:
    """Risques évalués, triés par criticité décroissante (déterministe)."""
    evalues = [
        RisqueEvalue(reference=r.id_externe, libelle=r.libelle, criticite=criticite(r),
                     niveau=niveau_criticite(criticite(r)))
        for r in risques
    ]
    return sorted(evalues, key=lambda e: e.criticite, reverse=True)


def statistiques_incidents(incidents: list[Incident]) -> dict:  # type: ignore[type-arg]
    avec_arret = [i for i in incidents if i.jours_arret > 0]
    return {
        "total": len(incidents),
        "par_type": dict(Counter(i.type_incident for i in incidents)),
        "par_gravite": dict(Counter(i.gravite for i in incidents)),
        "nb_avec_arret": len(avec_arret),
        "total_jours_arret": sum(i.jours_arret for i in incidents),
    }


def _ratio(numer: Decimal, heures: int) -> Decimal:
    if heures <= 0:
        return Decimal("0")
    return (numer / Decimal(heures)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def taux_frequence(incidents: list[Incident], *, heures_travaillees: int) -> Decimal:
    """TF = (accidents avec arrêt × 1 000 000) / heures travaillées."""
    nb = sum(1 for i in incidents if i.jours_arret > 0 and i.type_incident == "accident_travail")
    return _ratio(Decimal(nb) * Decimal("1000000"), heures_travaillees)


def taux_gravite(incidents: list[Incident], *, heures_travaillees: int) -> Decimal:
    """TG = (jours d'arrêt × 1000) / heures travaillées."""
    jours = sum(i.jours_arret for i in incidents)
    return _ratio(Decimal(jours) * Decimal("1000"), heures_travaillees)


# ============================================================ agent

class HseAgent:
    """Agent HSE/RSE : indicateurs déterministes + rédaction (plans, rapports)."""

    name = "erp.hse"
    prompt_file = "erp/hse.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def cartographier(self, risques: list[Risque]) -> list[RisqueEvalue]:
        return cartographie_risques(risques)

    def indicateurs(self, incidents: list[Incident], *, heures_travaillees: int | None = None) -> dict:  # type: ignore[type-arg]
        stats = statistiques_incidents(incidents)
        if heures_travaillees:
            stats["taux_frequence"] = taux_frequence(incidents, heures_travaillees=heures_travaillees)
            stats["taux_gravite"] = taux_gravite(incidents, heures_travaillees=heures_travaillees)
        return stats

    async def generer_plan_prevention(self, *, risques: list[RisqueEvalue], contexte: str = "") -> str:
        lignes = "\n".join(f"- [{r.niveau}] {r.libelle} (criticité {r.criticite})" for r in risques)
        ctx = f"Contexte : {contexte}\n" if contexte else ""
        user_msg = (
            f"Rédige un plan de prévention des risques (français).\n{ctx}"
            f"Risques (déjà évalués, ne pas recalculer la criticité) :\n{lignes}\n"
            "Pour chaque risque prioritaire : mesures de prévention/protection, responsable, échéance type. "
            "Traite d'abord les niveaux 'critique' et 'eleve'."
        )
        return await self._generate(user_msg, "generer_plan_prevention", max_tokens=1300)

    async def generer_rapport_durabilite(self, *, indicateurs: dict, periode: str) -> str:  # type: ignore[type-arg]
        user_msg = (
            f"--- Indicateurs HSE/RSE ({periode}, déjà calculés) ---\n{indicateurs}\n\n"
            "Rédige un rapport de durabilité (RSE) à partir de CES indicateurs uniquement : "
            "sécurité au travail, environnement, axes d'amélioration. N'invente aucun chiffre."
        )
        return await self._generate(user_msg, "generer_rapport_durabilite", max_tokens=1300)

    async def _generate(self, user_msg: str, op: str, *, max_tokens: int = 900) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "hse.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=max_tokens),
            )
            outcome = "ok"
            _log.info("hse_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
