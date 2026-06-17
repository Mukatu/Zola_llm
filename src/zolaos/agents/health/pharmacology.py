"""Sous-agent Pharmacologie — pôle Santé (V2.2 #48).

Réponses **génératives libres** (conformes à la garantie de capacités préservées) :
posologies, interactions, équivalences génériques LNME, contre-indications.
Sources RAG : CIM-10 OMS + LNME congolaise.

Garde-fou anti-hallucination strict : refus si pas de match RAG (santé = zéro
tolérance pour les conseils non sourcés).
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class PharmacologyAgent(RAGAgent):
    name = "health.pharmacology"
    rag_schema = "rag_health"
    prompt_file = "health/pharmacology.md"
    default_tags = ("country:cg", "module:pharmacology")
    requires_citation = True
    min_confidence = 0.50      # santé = exigeant
    top_k = 5
    max_tokens = 600
    temperature = 0.1          # très peu de créativité en pharma
