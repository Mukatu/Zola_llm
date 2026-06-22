"""Tests Secrétariat sociétaire (ERP, OPS-4) — moteur déterministe + agent."""

from __future__ import annotations

from datetime import date

import pytest

from zolaos.agents.erp.secretariat import (
    Mandat,
    SecretariatAgent,
    date_limite_ago,
    echeance_mandat,
    mandats_a_renouveler,
)
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient

AS_OF = date(2026, 2, 1)


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(content="Procès-verbal rédigé.", model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""
        return _g()

    async def health(self) -> bool:
        return True


def test_echeance_mandat() -> None:
    m = Mandat(id_externe="M1", titulaire="A. Mabiala", fonction="administrateur",
               date_nomination=date(2023, 3, 15), duree_annees=3)
    assert echeance_mandat(m) == date(2026, 3, 15)
    # Durée indéterminée → None
    assert echeance_mandat(Mandat(id_externe="M2", titulaire="X", date_nomination=date(2024, 1, 1))) is None


def test_date_limite_ago_six_mois() -> None:
    # Clôture 31/12/2025 → AGO au plus tard 30/06/2026 (AUSCGIE 6 mois)
    assert date_limite_ago(date(2025, 12, 31)) == date(2026, 6, 30)


def test_mandats_a_renouveler() -> None:
    mandats = [
        Mandat(id_externe="M1", titulaire="A", fonction="administrateur", date_nomination=date(2023, 3, 15), duree_annees=3),  # éch 2026-03-15 → +42 j
        Mandat(id_externe="M2", titulaire="B", fonction="gerant", date_nomination=date(2024, 1, 1), duree_annees=5),          # éch 2029 → hors horizon
    ]
    alertes = mandats_a_renouveler(mandats, as_of=AS_OF, horizon_jours=90)
    assert [a.reference for a in alertes] == ["M1"]


async def test_agent_generer_pv_sans_inventer() -> None:
    agent = SecretariatAgent(client=_CapturingClient(), settings=Settings())
    out = await agent.generer_pv(
        type_reunion="AGO", date_reunion=date(2026, 6, 20),
        resolutions=["Approbation des comptes 2025", "Affectation du résultat"],
        presents=["A. Mabiala", "B. Nkodia"],
    )
    assert "rédigé" in out
    assert "Approbation des comptes 2025" in agent._client.last  # type: ignore[attr-defined]
    assert "2026-06-20" in agent._client.last  # type: ignore[attr-defined]


async def test_agent_ordre_du_jour() -> None:
    agent = SecretariatAgent(client=_CapturingClient(), settings=Settings())
    await agent.generer_ordre_du_jour(type_reunion="CA", points=["Budget 2026", "Nomination DG"])
    assert "Budget 2026" in agent._client.last  # type: ignore[attr-defined]
    assert "CA" in agent._client.last  # type: ignore[attr-defined]
