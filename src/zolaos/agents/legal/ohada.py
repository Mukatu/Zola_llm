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
    forme_aware = True  # SARL/SA/coopérative… → boost par forme (évite SARL↔coop)
    # 0.50 (et non 0.55) : le texte AUSCGIE du dataset est OCR-dégradé, ce qui
    # plafonne les similarités cosinus (~0.50) même sur le BON article. Le boost
    # forme + le rerank hybride garantissent déjà le bon sous-corpus ; un seuil à
    # 0.55 ferait abandonner l'agent (→ filet de rattrapage sans boost, qui
    # laissait passer les coopératives). Aligné sur les agents génériques.
    min_confidence = 0.50
    top_k = 6
    max_tokens = 1200  # un peu plus pour les contrats
    temperature = 0.15
