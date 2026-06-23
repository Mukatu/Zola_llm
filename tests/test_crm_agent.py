"""Tests de l'agent CRM (CRM-2) : délégation déterministe + rédaction/narration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from zolaos.agents.crm.agent import CrmAgent
from zolaos.agents.crm.engine import RelanceItem
from zolaos.agents.crm.models import Opportunity
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient

AS_OF = date(2026, 2, 1)


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(
            content="Texte commercial généré.", model="fake", provider=self.provider
        )

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


def _opp(idx: str, montant: str, etape: str, *, derniere: date | None = None) -> Opportunity:
    return Opportunity(
        id_externe=idx,
        client="ACME",
        libelle=f"Deal {idx}",
        montant_xaf=Decimal(montant),
        etape=etape,
        derniere_interaction=derniere,
    )


@pytest.fixture
def agent() -> CrmAgent:
    return CrmAgent(client=_CapturingClient(), settings=Settings())


def test_pipeline_delegates(agent: CrmAgent) -> None:
    stats = agent.pipeline(
        [_opp("O1", "1000000", "prospection"), _opp("O2", "2000000", "negociation")]
    )
    assert stats.nb_open == 2
    assert stats.weighted_open_xaf == Decimal("1700000")


def test_prioritize_leads_sorted(agent: CrmAgent) -> None:
    opps = [
        _opp("low", "0", "prospection", derniere=date(2025, 1, 1)),
        _opp("high", "5000000", "negociation", derniere=AS_OF),
    ]
    ranked = agent.prioritize_leads(opps, as_of=AS_OF)
    assert ranked[0][0].id_externe == "high"
    assert ranked[0][1].score >= ranked[1][1].score


async def test_draft_relance_uses_context(agent: CrmAgent) -> None:
    item = RelanceItem("devis_expire", "Q1", "Devis D-Q1 expiré sans réponse", "high")
    out = await agent.draft_relance(item, client_nom="ACME SARL")
    assert "généré" in out
    assert "Devis D-Q1 expiré" in agent._client.last  # type: ignore[attr-defined]
    assert "ACME SARL" in agent._client.last  # type: ignore[attr-defined]


async def test_synthesize_pipeline_passes_numbers(agent: CrmAgent) -> None:
    stats = agent.pipeline([_opp("O2", "2000000", "negociation")])
    await agent.synthesize_pipeline(stats)
    assert "Valeur totale ouverte : 2000000 XAF" in agent._client.last  # type: ignore[attr-defined]
