"""Agent Marketing — couche IA (addendum §3.3, MKT-2).

Délègue le **déterministe** (segmentation, consentement) et n'utilise le LLM que
pour **générer du contenu** (offres, emailing, posts). **Privacy by design** :
`generate_campaign` refuse de produire une campagne ciblée sans audience
consentante (Loi 29-2019). Disponible profils box et cortex.
"""

from __future__ import annotations

import time
from datetime import date

from zolaos.agents._prompts import load_prompt
from zolaos.agents.mkt.consent import ConsentError, ConsentSummary, consent_summary, filter_consented
from zolaos.agents.mkt.models import MarketingContact
from zolaos.agents.mkt.segmentation import segment_contacts
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.mkt.agent")


class MarketingAgent:
    """Agent marketing : segmentation/consentement (déterministe) + contenu (LLM)."""

    name = "mkt.marketing"
    prompt_file = "mkt/marketing.md"

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    # ----------------------------------------------------- déterministe

    def segment(
        self, contacts: list[MarketingContact], *, as_of: date | None = None
    ) -> dict[str, list[MarketingContact]]:
        return segment_contacts(contacts, as_of=as_of)

    def eligible_audience(self, contacts: list[MarketingContact], finalite: str) -> list[MarketingContact]:
        return filter_consented(contacts, finalite)

    # ----------------------------------------------------- génératif (LLM)

    async def _generate(self, user_msg: str, op: str) -> str:
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await self._client.generate(
                [
                    Message(role="system", content=load_prompt("mkt", "marketing.md")),
                    Message(role="user", content=user_msg),
                ],
                model=self._settings.LLM_MODEL_BRIGADE,
                options=GenerationOptions(temperature=0.5, max_tokens=900),
            )
            outcome = "ok"
            _log.info("mkt_agent." + op, duration_seconds=time.perf_counter() - start)
            return result.content
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=self.name, outcome=outcome).inc()

    async def draft_content(self, *, canal: str, finalite: str, brief: str, segment_nom: str | None = None) -> str:
        """Contenu marketing générique (non ciblé nominativement)."""
        seg = f"Segment visé : {segment_nom}.\n" if segment_nom else ""
        user_msg = (
            f"Rédige un contenu marketing pour le canal '{canal}' (finalité : {finalite}).\n"
            f"{seg}Brief : {brief}\n"
            "Ton engageant et honnête, en français. Pas d'allégation trompeuse."
        )
        return await self._generate(user_msg, "draft_content")

    async def generate_campaign(
        self,
        *,
        contacts: list[MarketingContact],
        finalite: str,
        canal: str,
        brief: str,
        segment_nom: str | None = None,
    ) -> dict:  # type: ignore[type-arg]
        """Campagne ciblée — **garde consentement** : refuse si aucune audience éligible."""
        summary: ConsentSummary = consent_summary(contacts, finalite)
        if summary.eligibles == 0:
            raise ConsentError(
                f"Aucun contact consentant pour la finalité {finalite!r} "
                f"({summary.total} contacts, 0 éligible) — campagne refusée (Loi 29-2019)."
            )
        content = await self.draft_content(canal=canal, finalite=finalite, brief=brief, segment_nom=segment_nom)
        _log.info("mkt_agent.campaign", finalite=finalite, eligibles=summary.eligibles, exclus=summary.exclus)
        return {"content": content, "audience": summary}
