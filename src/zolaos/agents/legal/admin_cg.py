"""Sous-agent Droit administratif CG — pôle Droit, module admin_cg (V2.2 #64).

Capacités génératives V2.2 : analyses de marchés publics, contestation
administrative, contentieux marchés publics ARMP, conseils sur la conformité
des procédures gouvernementales et des entités publiques.

Sources RAG : Code des marchés publics CG, Lois de Finances, rapports
publics de la Cour des Comptes, recommandations ARMP (Autorité de
Régulation des Marchés Publics).

**Sensibilité politique élevée** : neutralité éditoriale stricte, refus de
toute qualification politique, factuel uniquement.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class AdminCgAgent(RAGAgent):
    name = "legal.admin_cg"
    rag_schema = "rag_legal"
    prompt_file = "legal/admin_cg.md"
    default_tags = ("country:cg", "module:admin_cg")
    requires_citation = True
    min_confidence = 0.60         # exigeant — sujet sensible
    top_k = 8
    max_tokens = 1500
    temperature = 0.05            # quasi-déterministe pour neutralité
