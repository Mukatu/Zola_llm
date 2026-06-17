"""Sous-agent Droit du travail CG — pôle Droit, module travail_cg (V2.2 #50).

Capacités génératives V2.2 : modèles CDI/CDD, lettres de licenciement, ruptures
conventionnelles, calculs d'indemnités, analyse de conventions collectives.

Sources RAG : Code du Travail CG 45/75 consolidé + Conventions Collectives
Nationales + jurisprudences Cour Suprême.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class TravailCgAgent(RAGAgent):
    name = "legal.travail_cg"
    rag_schema = "rag_legal"
    prompt_file = "legal/travail_cg.md"
    default_tags = ("country:cg", "module:travail_cg")
    requires_citation = True
    min_confidence = 0.55
    top_k = 6
    max_tokens = 1200
    temperature = 0.15
