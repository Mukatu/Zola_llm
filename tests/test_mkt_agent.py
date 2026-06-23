"""Tests Marketing MKT-2 : agent (génération de contenu + garde consentement)."""

from __future__ import annotations

import pytest

from zolaos.agents.mkt.agent import MarketingAgent
from zolaos.agents.mkt.consent import ConsentError
from zolaos.agents.mkt.models import MarketingContact
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(
            content="Objet : Offre spéciale\nBonjour…", model="fake", provider=self.provider
        )

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


def _c(idx: str, *, consent: bool, finalites: list[str]) -> MarketingContact:
    return MarketingContact(
        id_externe=idx, nom=f"C{idx}", consentement_marketing=consent, finalites=finalites
    )


@pytest.fixture
def agent() -> MarketingAgent:
    return MarketingAgent(client=_CapturingClient(), settings=Settings())


async def test_generate_campaign_with_consent(agent: MarketingAgent) -> None:
    contacts = [
        _c("1", consent=True, finalites=["promotions"]),
        _c("2", consent=False, finalites=[]),
    ]
    result = await agent.generate_campaign(
        contacts=contacts,
        finalite="promotions",
        canal="email",
        brief="Soldes de janvier",
    )
    assert "Offre spéciale" in result["content"]
    assert result["audience"].eligibles == 1
    assert result["audience"].exclus == 1
    assert "Soldes de janvier" in agent._client.last  # type: ignore[attr-defined]


async def test_generate_campaign_without_consent_refused(agent: MarketingAgent) -> None:
    contacts = [
        _c("1", consent=False, finalites=[]),
        _c("2", consent=True, finalites=["newsletter"]),
    ]
    # Aucune cible consentante pour 'promotions' → refus (privacy by design)
    with pytest.raises(ConsentError):
        await agent.generate_campaign(
            contacts=contacts,
            finalite="promotions",
            canal="email",
            brief="X",
        )


async def test_draft_content_ungated(agent: MarketingAgent) -> None:
    out = await agent.draft_content(canal="post", finalite="notoriete", brief="Lancement produit")
    assert "Offre spéciale" in out  # contenu généré (fake)
    assert "Lancement produit" in agent._client.last  # type: ignore[attr-defined]


def test_segment_and_eligible_delegation(agent: MarketingAgent) -> None:
    contacts = [_c("1", consent=True, finalites=["newsletter"])]
    assert agent.eligible_audience(contacts, "newsletter")[0].id_externe == "1"
    assert isinstance(agent.segment(contacts), dict)
