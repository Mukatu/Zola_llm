"""Sous-agent Reporting bailleurs — pôle GRC, module reporting_bailleurs (V2.2 #65).

Capacités génératives V2.2 : génération de rapports financiers/opérationnels
pour bailleurs internationaux (UE, ONU, Banque Mondiale, AFD, USAID, fondations),
conformité IATI, justification d'éligibilité PRAG, alignement logframe / ToC.

Sources RAG : standards IATI, guides PRAG UE, OECD-DAC, GAFI (anti-blanchiment
ONG), exigences spécifiques par bailleur.

Multi-langue prioritaire (FR + EN) — anticipation Pôle K.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class ReportingBailleursAgent(RAGAgent):
    name = "grc.reporting_bailleurs"
    rag_schema = "rag_legal"  # placeholder — rag_grc/rag_ong futur Phase 5
    prompt_file = "grc/reporting_bailleurs.md"
    default_tags = ("country:cg", "module:reporting_bailleurs")
    requires_citation = True
    min_confidence = 0.50  # sources moins canoniques (guides bailleurs variés)
    top_k = 8
    max_tokens = 2000
    temperature = 0.15
