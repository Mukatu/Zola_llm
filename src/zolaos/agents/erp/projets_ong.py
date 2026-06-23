"""Sous-agent Projets ONG — pôle ERP, module projets_ong (V2.2 #65).

Capacités génératives V2.2 : gestion financière simplifiée pour ONG (suivi
budget, ventilation par bailleur/projet/activité), génération de tableaux de
trésorerie multi-devises, calculs de change opérationnels, suivi des dépenses
éligibles par convention de financement.

Sources RAG : SYSCOHADA adapté ONG, guides OCED-DAC, normes IPSAS, conventions
de financement modèles.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class ProjetsOngAgent(RAGAgent):
    name = "erp.projets_ong"
    rag_schema = "rag_legal"  # placeholder — rag_erp futur Phase 4
    prompt_file = "erp/projets_ong.md"
    default_tags = ("country:cg", "module:projets_ong")
    requires_citation = True
    min_confidence = 0.50
    top_k = 8
    max_tokens = 1800
    temperature = 0.15
