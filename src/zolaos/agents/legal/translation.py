"""Traduction de documents (contrats étrangers) — pôle juridique.

Traduction **fidèle et orientée juridique** via le LLM. Les contrats dépassent la
fenêtre de contexte : on découpe en blocs (en respectant les paragraphes), on
traduit chaque bloc, on réassemble. Le service ne résume pas et n'ajoute aucun
commentaire — il rend la traduction.
"""

from __future__ import annotations

from dataclasses import dataclass

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.legal.translation")

_CHUNK = 3000  # caractères par bloc de traduction


@dataclass(frozen=True)
class TranslationResult:
    source_lang: str
    target_lang: str
    text: str


def decouper(texte: str, taille: int = _CHUNK) -> list[str]:
    """Découpe le texte en blocs ~`taille` caractères, aux frontières de paragraphe."""
    blocs: list[str] = []
    courant: list[str] = []
    n = 0
    for para in texte.split("\n\n"):
        if n + len(para) > taille and courant:
            blocs.append("\n\n".join(courant))
            courant, n = [], 0
        courant.append(para)
        n += len(para) + 2
    if courant:
        blocs.append("\n\n".join(courant))
    return blocs or [""]


class TranslationService:
    """Traducteur LLM (8B) — détection de langue + traduction juridique par blocs."""

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def detect_language(self, echantillon: str) -> str:
        """Détecte la langue source (nom en français) sur un échantillon."""
        result = await self._client.generate(
            [
                Message(
                    role="system",
                    content=(
                        "Tu identifies la langue d'un texte. Réponds UNIQUEMENT par le nom "
                        "de la langue en français (ex : anglais, portugais, mandarin, arabe)."
                    ),
                ),
                Message(role="user", content=echantillon[:800]),
            ],
            model=self._settings.LLM_MODEL_BRIGADE,
            options=GenerationOptions(temperature=0.0, max_tokens=12),
        )
        return (result.content.strip().splitlines()[0][:40] if result.content.strip() else "") or (
            "inconnue"
        )

    async def translate(
        self, texte: str, *, target_lang: str = "français", source_lang: str | None = None
    ) -> TranslationResult:
        """Traduit `texte` vers `target_lang` (langue source détectée si non fournie)."""
        src = source_lang or await self.detect_language(texte)
        system = (
            f"Tu es un traducteur juridique professionnel. Traduis fidèlement le texte "
            f"de {src} vers {target_lang}. Préserve la structure (articles, clauses, "
            f"numérotation), la terminologie juridique et le sens EXACT. Ne résume pas, "
            f"n'ajoute aucun commentaire ni note : rends UNIQUEMENT la traduction."
        )
        morceaux: list[str] = []
        blocs = decouper(texte)
        for bloc in blocs:
            result = await self._client.generate(
                [Message(role="system", content=system), Message(role="user", content=bloc)],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.1, max_tokens=2000),
            )
            morceaux.append(result.content.strip())
        _log.info(
            "translation.done", source=src, target=target_lang, blocs=len(blocs), chars=len(texte)
        )
        return TranslationResult(
            source_lang=src, target_lang=target_lang, text="\n\n".join(morceaux)
        )
