"""Moyens Généraux & Patrimoine / Facility — module ERP (OPS-3).

Maintenance préventive et suivi des échéances (assurances, visites techniques,
licences) des actifs (flotte, groupes électrogènes, parcs informatiques,
bâtiments). **Déterministe d'abord** : les dates et alertes sont calculées en
code ; le `FacilityAgent` rédige (ordres de travail) et synthétise.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.facility")

TypeActif = Literal["vehicule", "groupe_electrogene", "informatique", "batiment", "autre"]
TypeEcheance = Literal["assurance", "visite_technique", "licence", "contrat", "autre"]
Urgence = Literal["high", "medium", "low"]


# ============================================================ modèles

class Asset(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    libelle: str
    type_actif: TypeActif = "autre"
    maintenance_intervalle_jours: int = Field(default=0, ge=0, description="0 = pas de préventif")
    derniere_maintenance: date | None = None
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class Echeance(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    asset_id: str | None = None
    type_echeance: TypeEcheance = "autre"
    libelle: str
    date_echeance: date


@dataclass(frozen=True)
class FacilityAlerte:
    categorie: Literal["maintenance", "echeance"]
    reference: str
    libelle: str
    date_cible: date
    jours_restants: int          # négatif = en retard
    urgence: Urgence


# ============================================================ moteur (pur)

def prochaine_maintenance(asset: Asset) -> date | None:
    """Dernière maintenance + intervalle. None si non planifiable."""
    if asset.maintenance_intervalle_jours > 0 and asset.derniere_maintenance is not None:
        return asset.derniere_maintenance + timedelta(days=asset.maintenance_intervalle_jours)
    return None


def _urgence(jours: int) -> Urgence:
    if jours <= 7:        # en retard (négatif) ou imminent
        return "high"
    return "medium"


def maintenances_dues(
    assets: list[Asset], *, as_of: date | None = None, horizon_jours: int = 30
) -> list[FacilityAlerte]:
    as_of = as_of or date.today()
    out: list[FacilityAlerte] = []
    for a in assets:
        d = prochaine_maintenance(a)
        if d is None:
            continue
        jours = (d - as_of).days
        if jours <= horizon_jours:
            out.append(FacilityAlerte(
                categorie="maintenance", reference=a.id_externe,
                libelle=f"Maintenance préventive : {a.libelle}", date_cible=d,
                jours_restants=jours, urgence=_urgence(jours),
            ))
    return out


def echeances_dues(
    echeances: list[Echeance], *, as_of: date | None = None, horizon_jours: int = 30
) -> list[FacilityAlerte]:
    as_of = as_of or date.today()
    out: list[FacilityAlerte] = []
    for e in echeances:
        jours = (e.date_echeance - as_of).days
        if jours <= horizon_jours:
            out.append(FacilityAlerte(
                categorie="echeance", reference=e.id_externe,
                libelle=f"{e.type_echeance} : {e.libelle}", date_cible=e.date_echeance,
                jours_restants=jours, urgence=_urgence(jours),
            ))
    return out


# ============================================================ agent

class FacilityAgent:
    """Agent Moyens Généraux : échéancier déterministe + rédaction générative."""

    name = "erp.moyens_generaux"
    prompt_file = "erp/moyens_generaux.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def analyser(
        self, assets: list[Asset], echeances: list[Echeance], *,
        as_of: date | None = None, horizon_jours: int = 30,
    ) -> dict:  # type: ignore[type-arg]
        return {
            "maintenances": maintenances_dues(assets, as_of=as_of, horizon_jours=horizon_jours),
            "echeances": echeances_dues(echeances, as_of=as_of, horizon_jours=horizon_jours),
        }

    async def rediger_ordre_travail(self, alerte: FacilityAlerte) -> str:
        user_msg = (
            f"Rédige un ordre de travail (français).\n"
            f"Objet : {alerte.libelle}\nÉchéance : {alerte.date_cible} "
            f"({alerte.jours_restants} jours, urgence {alerte.urgence}).\n"
            "Sections : intervention demandée, priorité, consignes de sécurité. "
            "N'invente pas de date ; reprends celle fournie."
        )
        return await self._generate(user_msg, "rediger_ordre_travail")

    async def synthese(self, analyse: dict) -> str:  # type: ignore[type-arg]
        items = analyse["maintenances"] + analyse["echeances"]
        lignes = "\n".join(
            f"- [{a.urgence}] {a.libelle} — {a.date_cible} ({a.jours_restants} j)" for a in items
        )
        user_msg = (
            f"--- Échéancier moyens généraux (déjà calculé) ---\n"
            f"Maintenances : {len(analyse['maintenances'])} | Échéances : {len(analyse['echeances'])}\n{lignes}\n\n"
            "Rédige une synthèse : priorités, retards, renouvellements à anticiper. N'invente aucune date."
        )
        return await self._generate(user_msg, "synthese")

    async def _generate(self, user_msg: str, op: str) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "moyens_generaux.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=800),
            )
            outcome = "ok"
            _log.info("facility_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
