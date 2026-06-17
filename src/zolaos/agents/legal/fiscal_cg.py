"""Sous-agent Droit fiscal CG — pôle Droit, module fiscal_cg (V2.2 #51).

Capacités génératives V2.2 : déclarations TVA / IS / IRPP / retenues à la
source, analyse d'optimisations licites, simulation d'imposition, analyse de
liasses fiscales.

Sources RAG : CGI congolais + dernière Loi de Finances + jurisprudences fiscales.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class FiscalCgAgent(RAGAgent):
    name = "legal.fiscal_cg"
    rag_schema = "rag_legal"
    prompt_file = "legal/fiscal_cg.md"
    default_tags = ("country:cg", "module:fiscal_cg")
    requires_citation = True
    min_confidence = 0.55
    top_k = 6
    max_tokens = 1200
    temperature = 0.15
