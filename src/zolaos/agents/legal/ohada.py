"""Sous-agent Droit OHADA — pôle Droit, module ohada (V2.2 #49).

Capacités génératives V2.2 : rédaction de clauses, analyse de contrats, conseils
sur les 9 actes uniformes OHADA (sociétés, sûretés, droit commercial,
recouvrement, procédures collectives, arbitrage, comptable, transport).

Sources RAG : Actes uniformes OHADA + jurisprudences CCJA. Citation obligatoire.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class OhadaAgent(RAGAgent):
    name = "legal.ohada"
    rag_schema = "rag_legal"
    prompt_file = "legal/ohada.md"
    default_tags = ("country:cg", "module:ohada")
    requires_citation = True
    min_confidence = 0.55  # juridique = précision exigée
    top_k = 6
    max_tokens = 1200  # un peu plus pour les contrats
    temperature = 0.15
