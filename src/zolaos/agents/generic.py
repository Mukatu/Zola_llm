"""Agents génériques de pôle — filet structurel de l'orchestrateur.

Quand le routeur ne fournit **pas** de `module` précis, on ne tombe plus sur
l'agent placeholder (sans RAG, sans citations) : un agent générique interroge
**tout le corpus du pôle** (`country:cg`, sans filtre module) et ancre sa réponse.
S'il ne trouve rien de solide (`requires_citation` + `min_confidence`), une
`InsufficientContextError` fait retomber l'orchestrateur proprement sur l'agent
générique. Le corpus du client (rag_tenant) est fusionné comme pour tout agent RAG.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class GenericLegalAgent(RAGAgent):
    name = "legal.generique"
    rag_schema = "rag_legal"
    prompt_file = "legal/generique.md"
    default_tags = ("country:cg",)  # tout le corpus juridique, pas de filtre module
    requires_citation = True
    # Une question de droit du travail non pinnée sur `travail_cg` (ex. « congés
    # dans le secteur minier » → legal/None) peut quand même nommer un secteur :
    # on écarte alors le bruit des autres conventions. Idem une question OHADA non
    # pinnée sur `ohada` peut nommer une forme de société. Sans effet sur les
    # textes qui ne portent pas les tags secteur:/forme: (fiscaux, etc.).
    sector_aware = True
    forme_aware = True
    min_confidence = 0.5
    top_k = 6
    max_tokens = 1200
    temperature = 0.15


class GenericErpAgent(RAGAgent):
    name = "erp.generique"
    rag_schema = "rag_erp"
    prompt_file = "erp/generique.md"
    default_tags = ("country:cg",)
    requires_citation = True
    min_confidence = 0.5
    top_k = 6
    max_tokens = 1200
    temperature = 0.15


class GenericHealthAgent(RAGAgent):
    name = "health.generique"
    rag_schema = "rag_health"
    prompt_file = "health/generique.md"
    default_tags = ("country:cg",)
    requires_citation = True
    min_confidence = 0.5
    top_k = 6
    max_tokens = 1200
    temperature = 0.15


class GenericFintechAgent(RAGAgent):
    """Ancre les questions fintech sur le corpus réglementaire (COBAC/GABAC/BEAC)."""

    name = "fintech.generique"
    rag_schema = "rag_fintech"
    prompt_file = "fintech/generique.md"
    default_tags = ("country:cg",)
    requires_citation = True
    min_confidence = 0.5
    top_k = 6
    max_tokens = 1200
    temperature = 0.15
