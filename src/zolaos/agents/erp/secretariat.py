"""Secrétariat sociétaire / Corporate Governance — module ERP (OPS-4).

Vie administrative légale de l'entreprise elle-même (distinct du pôle Droit
doctrinal). **Déterministe d'abord** : registre des mandats sociaux + échéancier
légal (renouvellement des mandats, date limite de l'AGO selon l'AUSCGIE OHADA).
Le `SecretariatAgent` **rédige** (PV d'AG/CA, ordres du jour) — il ne calcule pas
les dates.
"""

from __future__ import annotations

import calendar
import time
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from zolaos.agents._prompts import load_prompt
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.erp.secretariat")

Fonction = Literal["gerant", "administrateur", "president_ca", "directeur_general", "commissaire_comptes", "autre"]
TypeReunion = Literal["AGO", "AGE", "CA"]
Urgence = Literal["high", "medium", "low"]

# AUSCGIE : l'AGO d'approbation des comptes se tient dans les 6 mois de la clôture.
DELAI_AGO_MOIS = 6


# ============================================================ modèles

class Mandat(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    titulaire: str
    fonction: Fonction = "autre"
    date_nomination: date
    duree_annees: int = Field(default=0, ge=0, description="0 = durée indéterminée")
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


@dataclass(frozen=True)
class SecretariatAlerte:
    categorie: Literal["mandat", "ago"]
    reference: str
    libelle: str
    date_cible: date
    jours_restants: int          # négatif = dépassé
    urgence: Urgence


# ============================================================ helpers dates

def _add_years(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29 février
        return d.replace(year=d.year + n, day=28)


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


# ============================================================ moteur (pur)

def echeance_mandat(mandat: Mandat) -> date | None:
    """Fin du mandat = nomination + durée. None si durée indéterminée."""
    if mandat.duree_annees <= 0:
        return None
    return _add_years(mandat.date_nomination, mandat.duree_annees)


def date_limite_ago(date_cloture_exercice: date, *, delai_mois: int = DELAI_AGO_MOIS) -> date:
    """Date limite de tenue de l'AGO d'approbation des comptes (AUSCGIE : 6 mois)."""
    return _add_months(date_cloture_exercice, delai_mois)


def _urgence(jours: int, *, seuil_high: int) -> Urgence:
    return "high" if jours <= seuil_high else "medium"


def mandats_a_renouveler(
    mandats: list[Mandat], *, as_of: date | None = None, horizon_jours: int = 90
) -> list[SecretariatAlerte]:
    as_of = as_of or date.today()
    out: list[SecretariatAlerte] = []
    for m in mandats:
        ech = echeance_mandat(m)
        if ech is None:
            continue
        jours = (ech - as_of).days
        if jours <= horizon_jours:
            out.append(SecretariatAlerte(
                categorie="mandat", reference=m.id_externe,
                libelle=f"Mandat {m.fonction} de {m.titulaire} à renouveler", date_cible=ech,
                jours_restants=jours, urgence=_urgence(jours, seuil_high=30),
            ))
    return out


def echeance_ago(
    date_cloture_exercice: date, *, as_of: date | None = None
) -> SecretariatAlerte:
    """Alerte sur l'AGO d'approbation des comptes (date limite AUSCGIE)."""
    as_of = as_of or date.today()
    limite = date_limite_ago(date_cloture_exercice)
    jours = (limite - as_of).days
    return SecretariatAlerte(
        categorie="ago", reference=f"AGO-{date_cloture_exercice.year}",
        libelle="AGO d'approbation des comptes (délai légal AUSCGIE)", date_cible=limite,
        jours_restants=jours, urgence=_urgence(jours, seuil_high=30),
    )


# ============================================================ agent

class SecretariatAgent:
    """Agent Secrétariat sociétaire : échéancier déterministe + rédaction (PV/ODJ)."""

    name = "erp.secretariat_societaire"
    prompt_file = "erp/secretariat_societaire.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def echeancier(
        self, mandats: list[Mandat], *, date_cloture_exercice: date | None = None,
        as_of: date | None = None, horizon_jours: int = 90,
    ) -> list[SecretariatAlerte]:
        out = mandats_a_renouveler(mandats, as_of=as_of, horizon_jours=horizon_jours)
        if date_cloture_exercice is not None:
            out.append(echeance_ago(date_cloture_exercice, as_of=as_of))
        return out

    async def generer_ordre_du_jour(self, *, type_reunion: TypeReunion, points: list[str]) -> str:
        pts = "\n".join(f"- {p}" for p in points)
        user_msg = (
            f"Rédige l'ordre du jour d'une réunion {type_reunion} (français, cadre AUSCGIE OHADA).\n"
            f"Points à inscrire :\n{pts}\n"
            "Structure formelle. N'ajoute pas de résolution non demandée."
        )
        return await self._generate(user_msg, "generer_ordre_du_jour")

    async def generer_pv(
        self, *, type_reunion: TypeReunion, date_reunion: date,
        resolutions: list[str], presents: list[str] | None = None,
    ) -> str:
        res = "\n".join(f"- {r}" for r in resolutions)
        pres = ("Présents : " + ", ".join(presents) + "\n") if presents else ""
        user_msg = (
            f"Rédige un procès-verbal de {type_reunion} (français, cadre AUSCGIE OHADA).\n"
            f"Date : {date_reunion}\n{pres}Résolutions adoptées :\n{res}\n"
            "Mentions usuelles (quorum, ordre du jour, votes, clôture). N'invente pas de date "
            "ni de résolution non fournie. À faire valider/signer par les organes compétents."
        )
        return await self._generate(user_msg, "generer_pv", max_tokens=1400)

    async def _generate(self, user_msg: str, op: str, *, max_tokens: int = 900) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("erp", "secretariat_societaire.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.2, max_tokens=max_tokens),
            )
            outcome = "ok"
            _log.info("secretariat_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()
