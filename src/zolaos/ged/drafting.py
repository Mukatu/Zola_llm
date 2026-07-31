"""Rédaction assistée d'un livrable — le « + » IA, ancré sur le corpus.

On réutilise le **RAGAgent public** (retrieve + garde-fous d'abstention + citations)
avec un prompt de rédaction : le LLM **narre et cite** à partir des textes de
référence, s'**abstient** si le corpus ne couvre pas le sujet, et n'invente RIEN
(surtout pas de valeurs chiffrées/juridiques). Servi **localement** (souveraineté).

Le pôle détermine le corpus (rag_legal/erp/…) ; l'abstention (`InsufficientContext`)
tombe AVANT toute génération. Le résultat est un **projet** que l'humain relit et
valide (doctrine « je cite, je ne tranche pas ») — jamais publié automatiquement.
"""

from __future__ import annotations

from zolaos.agents.rag_agent import RAGAgent

# Pôle → (schéma RAG de référence, tags requis). Corpus PUBLICS de référence.
POLE_SCHEMAS: dict[str, tuple[str, list[str]]] = {
    "droit": ("rag_legal", ["country:cg"]),
    "erp": ("rag_erp", ["country:cg"]),
    "sante": ("rag_health", ["country:cg"]),
    "cyber": ("rag_cyber", ["country:cg"]),
    "fintech": ("rag_fintech", ["country:cg"]),
}

_DRAFT_SYSTEM_PROMPT = (
    "Tu es un rédacteur pour un cabinet de conseil/audit en République du Congo. "
    "Tu produis le PROJET d'un livrable professionnel, en français, à partir des "
    "TEXTES DE RÉFÉRENCE fournis. Règles impératives :\n"
    "- Appuie-toi STRICTEMENT sur les textes ci-dessus ; cite chaque affirmation "
    "avec son numéro entre crochets, ex. [1], [2].\n"
    "- N'invente RIEN : aucune valeur chiffrée, aucun seuil, aucune référence "
    "d'article qui ne figure pas dans les textes. Si un point n'est pas couvert, "
    "écris-le explicitement (« à compléter — non couvert par les sources »).\n"
    "- Structure le livrable en sections (titres markdown ##) fidèles à la demande.\n"
    "- Style sobre et professionnel. Ce n'est qu'un PROJET, à relire par un consultant.\n"
    "- N'évoque aucun mécanisme interne (ne dis pas « RAG », « extraits », « contexte »)."
)


def pole_from_offre(offre: str | None) -> str:
    """Devine le pôle (corpus) à partir du type de mission (heuristique ; défaut droit)."""
    o = (offre or "").lower()
    if any(k in o for k in ("cyber", "secu", "iso27", "nist", "ssi")):
        return "cyber"
    if any(k in o for k in ("fintech", "microfinance", "aml", "kyc", "cobac", "emf")):
        return "fintech"
    if any(k in o for k in ("sante", "health", "pharma", "clinique", "medic")):
        return "sante"
    if any(k in o for k in ("fiscal", "compta", "paie", "syscohada", "audcif", "erp", "financ")):
        return "erp"
    return "droit"


def schema_for(pole: str) -> tuple[str, list[str]]:
    """(schéma, tags) du pôle ; défaut « droit » si inconnu."""
    schema, tags = POLE_SCHEMAS.get(pole, POLE_SCHEMAS["droit"])
    return schema, list(tags)


def build_draft_query(title: str, content: str, offre: str | None) -> str:
    """Construit la requête de rédaction (titre + sections du squelette + mission)."""
    sections = [line[3:].strip() for line in (content or "").splitlines() if line.startswith("## ")]
    sec_part = (" Sections à couvrir : " + " ; ".join(sections) + ".") if sections else ""
    return (
        f"Rédige le projet de « {title} » pour une mission « {offre or 'conseil'} », "
        f"en français, ancré sur les textes de référence applicables.{sec_part}"
    )


def assemble_draft(generated: str, citations: list) -> str:  # type: ignore[type-arg]
    """Corps rédigé + annexe des sources citées (markdown)."""
    body = generated.strip()
    if citations:
        refs = "\n".join(
            f"[{c.index}] {c.source_id or c.source_uri} (extrait {c.chunk_index})"
            for c in citations
        )
        body += "\n\n---\n\n**Sources**\n\n" + refs
    return body + "\n"


class DeliverableDraftAgent(RAGAgent):
    """Agent de rédaction de livrable : RAGAgent + prompt de rédaction inline.

    `requires_citation=True` → **abstention** si le corpus ne rend aucun extrait
    (pas de rédaction hors sources). Le schéma/tags sont fixés à l'instanciation."""

    requires_citation = True
    max_tokens = 1200
    temperature = 0.2

    def __init__(self, client, settings, *, schema: str, tags: list[str]) -> None:  # type: ignore[no-untyped-def]
        # Attributs d'instance qui masquent les ClassVar (schéma dynamique par pôle).
        self.name = "ged.draft"
        self.rag_schema = schema
        self.prompt_file = "inline"  # non chargé : _system_prompt est surchargé
        self.default_tags = tuple(tags)
        super().__init__(client, settings)

    @property
    def _system_prompt(self) -> str:  # surcharge la cached_property du parent
        return _DRAFT_SYSTEM_PROMPT
