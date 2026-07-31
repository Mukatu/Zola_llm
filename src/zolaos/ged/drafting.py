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

from dataclasses import dataclass, field
from typing import Any

from zolaos.agents.rag_agent import Citation, InsufficientContextError, RAGAgent
from zolaos.core.logging import get_logger
from zolaos.llm.factory import make_router_client

_log = get_logger("zolaos.ged.drafting")

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


_PROPOSAL_SYSTEM_PROMPT = (
    "Tu rédiges une PROPOSITION COMMERCIALE (lettre de mission) pour un cabinet de "
    "conseil/audit en République du Congo, en français, à partir des TEXTES DE "
    "RÉFÉRENCE fournis. Structure : contexte réglementaire, compréhension du besoin, "
    "approche/méthodologie, livrables attendus, cadre déontologique. Règles impératives :\n"
    "- Appuie le contexte réglementaire STRICTEMENT sur les textes ci-dessus ; cite "
    "avec leur numéro entre crochets, ex. [1], [2].\n"
    "- Ne PROPOSE AUCUN MONTANT d'honoraires ni prix : le chiffrage est une décision "
    "du cabinet, hors de ton champ. N'invente aucune valeur chiffrée ni référence.\n"
    "- Si un point réglementaire n'est pas couvert par les textes, ne l'affirme pas.\n"
    "- Ton professionnel et engageant, mais sobre. Ce n'est qu'un PROJET, à relire.\n"
    "- N'évoque aucun mécanisme interne (ne dis pas « RAG », « extraits », « contexte »)."
)


_REVIEW_SYSTEM_PROMPT = (
    "Tu es relecteur QUALITÉ pour un cabinet de conseil/audit. On te soumet un PROJET "
    "de livrable et des TEXTES DE RÉFÉRENCE. Ta tâche : CONFRONTER le projet aux textes "
    "— tu ne réécris PAS le livrable. Rends une revue structurée en français, en trois "
    "rubriques markdown :\n"
    "## Bien étayé\nLes affirmations du projet appuyées par les textes (cite [1], [2]).\n"
    "## À vérifier / non étayé\nLes affirmations du projet qui NE figurent PAS dans les "
    "textes (risque d'invention, notamment valeurs chiffrées et références d'articles) — "
    "liste-les explicitement.\n"
    "## Points manquants\nLes obligations importantes des textes absentes du projet.\n"
    "Sois précis et sobre. Ne réécris pas le livrable. N'évoque aucun mécanisme interne."
)

# Le contenu relu est tronqué pour tenir dans le contexte du modèle (avec les extraits).
_REVIEW_CONTENT_MAX = 4000


def build_review_query(title: str, content: str) -> str:
    """Requête de relecture : le projet à confronter aux textes de référence."""
    body = (content or "").strip()
    if len(body) > _REVIEW_CONTENT_MAX:
        body = body[:_REVIEW_CONTENT_MAX] + "\n…(projet tronqué pour la relecture)"
    return (
        f"Projet à relire — « {title} » :\n\n{body}\n\n"
        "Relis ce projet au regard des textes de référence ci-dessus : ce qui est bien "
        "étayé, ce qui est à vérifier / non étayé, ce qui manque. Ne le réécris pas."
    )


_MEMO_SYSTEM_PROMPT = (
    "Tu rédiges une NOTE / MÉMO réglementaire pour un cabinet de conseil/audit en "
    "République du Congo, en réponse à une QUESTION précise, à partir des TEXTES DE "
    "RÉFÉRENCE fournis. Structure en français, markdown :\n"
    "## Réponse\nUne réponse synthétique et directe à la question.\n"
    "## Fondement\nLe développement, chaque point cité [1], [2].\n"
    "## À vérifier / limites\nLes aspects de la question NON couverts par les textes.\n"
    "Règles : réponds UNIQUEMENT d'après les textes ci-dessus ; si la réponse n'y "
    "figure pas, dis-le explicitement plutôt que de l'inventer. Aucune valeur chiffrée "
    "ni référence d'article hors des textes. N'évoque aucun mécanisme interne."
)


def build_memo_query(question: str) -> str:
    """Requête d'un mémo réglementaire : la question, à ancrer sur le corpus."""
    q = (question or "").strip()
    return (
        f"Question : {q}\n\n"
        "Réponds par une note réglementaire, en t'appuyant STRICTEMENT sur les textes "
        "de référence ci-dessus, avec citations. Si la réponse n'y figure pas, indique-le."
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


def build_proposal_query(title: str, offre: str | None, client: str | None = None) -> str:
    """Requête de rédaction d'une proposition commerciale (ancrée sur le corpus)."""
    client_part = f" pour le client « {client} »" if client else ""
    return (
        f"Rédige une proposition commerciale (lettre de mission) « {title} »{client_part}, "
        f"pour une mission « {offre or 'conseil'} », en français : contexte réglementaire, "
        "compréhension du besoin, approche/méthodologie, livrables et cadre déontologique, "
        "ancrée sur les textes de référence applicables. Ne chiffre aucun honoraire."
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

    def __init__(  # type: ignore[no-untyped-def]
        self, client, settings, *, schema: str, tags: list[str], system_prompt: str | None = None
    ) -> None:
        # Attributs d'instance qui masquent les ClassVar (schéma dynamique par pôle).
        self.name = "ged.draft"
        self.rag_schema = schema
        self.prompt_file = "inline"  # non chargé : _system_prompt est surchargé
        self.default_tags = tuple(tags)
        self._prompt = system_prompt or _DRAFT_SYSTEM_PROMPT
        super().__init__(client, settings)

    @property
    def _system_prompt(self) -> str:  # surcharge la cached_property du parent
        return self._prompt


@dataclass
class DraftOutcome:
    """Résultat d'une rédaction assistée (générique livrable/proposition)."""

    status: str  # generated | abstained | unavailable
    content: str = ""
    citations: list[Citation] = field(default_factory=list)


async def run_draft(
    settings: Any,
    *,
    schema: str,
    tags: list[str],
    query: str,
    system_prompt: str | None = None,
    k: int = 8,
) -> DraftOutcome:
    """Exécute une rédaction ancrée : retrieve + abstention + génération + assemblage.

    Ne lève jamais : `abstained` si le corpus ne couvre pas (garde-fou AVANT toute
    génération), `unavailable` si le retrieval/LLM est indisponible, `generated` sinon.
    Patron réutilisable pour toute surface (livrable, proposition…)."""
    agent = DeliverableDraftAgent(
        make_router_client(settings),
        settings,
        schema=schema,
        tags=tags,
        system_prompt=system_prompt,
    )
    try:
        prepared = await agent.prepare(query, k=k)
    except InsufficientContextError:
        return DraftOutcome("abstained")
    except Exception as exc:  # retrieval/embeddings indisponibles
        _log.warning("draft.retrieve_unavailable", error=str(exc))
        return DraftOutcome("unavailable")
    try:
        result = await agent.answer_prepared(prepared)
    except Exception as exc:  # LLM local indisponible
        _log.warning("draft.llm_unavailable", error=str(exc))
        return DraftOutcome("unavailable", citations=list(prepared.citations))
    return DraftOutcome(
        "generated",
        content=assemble_draft(result.content, result.citations),
        citations=list(result.citations),
    )


# Exposés pour les endpoints (proposition, relecture qualité, mémo réglementaire).
PROPOSAL_SYSTEM_PROMPT = _PROPOSAL_SYSTEM_PROMPT
REVIEW_SYSTEM_PROMPT = _REVIEW_SYSTEM_PROMPT
MEMO_SYSTEM_PROMPT = _MEMO_SYSTEM_PROMPT
