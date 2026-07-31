"""Synthèse d'entretien — notes brutes → compte rendu structuré (savable).

Non-RAG : l'IA **met au propre** les notes fournies par le consultant (entretien
client, réunion, atelier) en un compte rendu professionnel — contexte, points
clés, décisions, prochaines étapes. Garde-fou propre à la reformulation : elle
structure **uniquement ce qui figure dans les notes**, n'invente aucune décision,
action, date ni participant non mentionné (« — non précisé » sinon).

Servi localement (souveraineté). Ne lève jamais : `unavailable` si le LLM échoue.
Le compte rendu produit est un **projet** que le consultant relit et valide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zolaos.core.logging import get_logger
from zolaos.llm.base import GenerationOptions, Message
from zolaos.llm.factory import make_router_client

_log = get_logger("zolaos.ged.synthesis")

# Types d'échange (bornés) → libellé pour le cadrage du prompt.
_KIND_LABELS = {
    "entretien": "entretien client",
    "reunion": "réunion",
    "atelier": "atelier",
    "appel": "échange téléphonique",
}
KINDS = frozenset(_KIND_LABELS)
_MAX_NOTES = 8000

_SYSTEM_PROMPT_TMPL = (
    "Tu es assistant d'un cabinet de conseil en République du Congo. À partir des "
    "NOTES BRUTES d'un {label}, rédige un COMPTE RENDU professionnel en français "
    "(markdown), avec les sections : ## Contexte, ## Points clés, ## Décisions, "
    "## Prochaines étapes (chaque étape avec responsable et échéance SI mentionnés). "
    "Règle absolue : structure UNIQUEMENT ce qui figure dans les notes ; n'invente "
    "aucune décision, action, date ni participant non mentionné. Si une section n'a "
    "pas de contenu dans les notes, écris « — non précisé ». Sois fidèle, sobre et "
    "concis. N'évoque aucun mécanisme interne."
)


def normalize_kind(kind: str | None) -> str:
    """Ramène le type d'échange à une valeur connue (défaut : entretien)."""
    return kind if kind in KINDS else "entretien"


def _system_prompt(kind: str) -> str:
    return _SYSTEM_PROMPT_TMPL.format(label=_KIND_LABELS[normalize_kind(kind)])


def build_synthesis_prompt(notes: str, kind: str) -> str:
    """Message utilisateur : les notes brutes (tronquées) à mettre au propre."""
    label = _KIND_LABELS[normalize_kind(kind)]
    body = (notes or "").strip()[:_MAX_NOTES]
    return (
        f"Notes brutes de l'{label} à mettre au propre :\n\n{body}\n\n"
        "Rédige le compte rendu structuré, fidèle aux notes."
    )


def default_title(kind: str) -> str:
    """Titre par défaut d'un compte rendu (dérivé du type d'échange)."""
    label = _KIND_LABELS[normalize_kind(kind)].capitalize()
    return f"Compte rendu — {label}"


@dataclass
class SynthesisOutcome:
    """Résultat d'une synthèse (compte rendu structuré)."""

    status: str  # generated | unavailable
    content: str = ""


async def run_synthesis(
    settings: Any, *, notes: str, kind: str = "entretien"
) -> SynthesisOutcome:
    """Met au propre des notes en compte rendu structuré (LLM local, hors-RAG).

    Ne lève jamais : `unavailable` si le LLM est indisponible, `generated` sinon."""
    client = make_router_client(settings)
    try:
        result = await client.generate(
            [
                Message(role="system", content=_system_prompt(kind)),
                Message(role="user", content=build_synthesis_prompt(notes, kind)),
            ],
            model=settings.LLM_MODEL_BRIGADE,
            options=GenerationOptions(temperature=0.2, max_tokens=1200),
        )
    except Exception as exc:  # LLM local indisponible
        _log.warning("synthesis.unavailable", error=str(exc))
        return SynthesisOutcome("unavailable")
    return SynthesisOutcome("generated", content=result.content.strip() + "\n")
