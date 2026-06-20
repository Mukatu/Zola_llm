"""Sous-agent RH — pôle ERP, module rh (V2.2 §4.1).

Cœur opérationnel RH de l'ERP : **mode rédaction** (génératif + citations) ancré
sur le corpus droit du travail CG (réutilisé via `rag_legal`, module
`travail_cg`). Couvre la génération de documents RH et le contrôle de conformité.

Capacités V2.2 §4.1 :
- Fiches de poste, lettres d'embauche
- Contrats CDI/CDD (génération conforme Code du travail CG + OHADA)
- Notifications disciplinaires (procédure sécurisée)
- Contrôle de conformité d'un contrat existant
- Aide au tri de CV (analyse structurée, anti-biais)

Garde-fous (cf. `docs/LEGAL_TASK_MODES.md`) : citation obligatoire, jurisprudence
en garde-fou de sécurisation, **assistance et non substitution** (un juriste/RH
valide avant usage réel). Le calcul de paie déterministe (CNSS/CIPRES/IRPP) est
traité séparément (jalon RH-2, moteur `ref`), pas par cet agent génératif.

`rag_schema="rag_legal"` : réutilise le corpus travail_cg (pas de `rag_erp`
nécessaire pour la rédaction juridiquement fondée).
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent


class RhAgent(RAGAgent):
    name = "erp.rh"
    rag_schema = "rag_legal"
    prompt_file = "erp/rh.md"
    default_tags = ("country:cg", "module:travail_cg")
    requires_citation = True
    min_confidence = 0.50
    top_k = 6
    max_tokens = 1600
    temperature = 0.15
