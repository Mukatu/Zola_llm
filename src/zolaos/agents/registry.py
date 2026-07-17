"""Registre de dispatch : module métier → agent RAG concret.

Permet à l'orchestrateur de router une requête vers l'agent RAG qui **ancre** sa
réponse sur le corpus ingéré (retrieval + citations), au lieu de l'agent
générique sans source. Le module vient du routeur (`RouteDecision.module`).

Un module absent de la table (ou `None`) → **filet structurel** : on tente
l'agent générique du pôle (`default_rag_agent_for`) qui interroge tout le corpus
du pôle. S'il n'ancre rien, l'orchestrateur retombe sur l'agent générique.
"""

from __future__ import annotations

from zolaos.agents.erp.compta import ComptaAgent
from zolaos.agents.erp.projets_ong import ProjetsOngAgent
from zolaos.agents.erp.rh import RhAgent
from zolaos.agents.generic import (
    GenericErpAgent,
    GenericFintechAgent,
    GenericHealthAgent,
    GenericLegalAgent,
)
from zolaos.agents.grc.reporting_bailleurs import ReportingBailleursAgent
from zolaos.agents.health.pharmacology import PharmacologyAgent
from zolaos.agents.legal.admin_cg import AdminCgAgent
from zolaos.agents.legal.fiscal_cg import FiscalCgAgent
from zolaos.agents.legal.ohada import OhadaAgent
from zolaos.agents.legal.travail_cg import TravailCgAgent
from zolaos.agents.rag_agent import RAGAgent
from zolaos.agents.router import Pole

# module (tel que renvoyé par le routeur) → classe d'agent RAG.
MODULE_AGENTS: dict[str, type[RAGAgent]] = {
    "ohada": OhadaAgent,
    "fiscal_cg": FiscalCgAgent,
    "travail_cg": TravailCgAgent,
    "admin_cg": AdminCgAgent,
    "pharmacology": PharmacologyAgent,
    "compta": ComptaAgent,
    "rh": RhAgent,  # réutilise le corpus travail_cg
    "projets_ong": ProjetsOngAgent,
    "reporting_bailleurs": ReportingBailleursAgent,
}


def rag_agent_for(module: str | None) -> type[RAGAgent] | None:
    """Retourne la classe d'agent RAG pour un module, ou None si aucun."""
    if not module:
        return None
    return MODULE_AGENTS.get(module)


# Filet structurel : agent générique par pôle (interroge tout le corpus du pôle)
# quand le routeur ne précise pas de module. Évite de tomber sur l'agent
# placeholder sans RAG pour un pôle qui possède pourtant un corpus.
POLE_DEFAULT_AGENTS: dict[Pole, type[RAGAgent]] = {
    Pole.LEGAL: GenericLegalAgent,
    Pole.ERP: GenericErpAgent,
    Pole.HEALTH: GenericHealthAgent,
    Pole.FINTECH: GenericFintechAgent,
}


def default_rag_agent_for(pole: Pole) -> type[RAGAgent] | None:
    """Agent RAG générique du pôle (filet quand `module` est absent), ou None."""
    return POLE_DEFAULT_AGENTS.get(pole)


# Corpus réglementaires **publics** (référence, pas de données client) balayés par
# le filet de rattrapage de l'orchestrateur quand le routeur envoie une requête
# vers un pôle sans corpus. Chaque schéma → l'agent générique qui porte le bon
# prompt (citations) et les bons garde-fous. `rag_tenant` en est exclu : il est
# cloisonné par client et ne doit jamais fuiter via un balayage transverse.
SCHEMA_GENERIC_AGENTS: dict[str, type[RAGAgent]] = {
    "rag_legal": GenericLegalAgent,
    "rag_fintech": GenericFintechAgent,
    "rag_erp": GenericErpAgent,
    "rag_health": GenericHealthAgent,
}


def public_regulatory_schemas() -> list[str]:
    """Schémas publics à balayer en rattrapage (ordre = priorité en cas d'égalité)."""
    return list(SCHEMA_GENERIC_AGENTS)


def generic_agent_for_schema(schema: str) -> type[RAGAgent] | None:
    """Agent générique portant le prompt/garde-fous d'un schéma public, ou None."""
    return SCHEMA_GENERIC_AGENTS.get(schema)
