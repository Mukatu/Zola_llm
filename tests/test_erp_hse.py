"""Tests HSE / RSE (ERP, OPS-5) — moteur déterministe + agent."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from zolaos.agents.erp.hse import (
    HseAgent,
    Incident,
    Risque,
    cartographie_risques,
    criticite,
    niveau_criticite,
    statistiques_incidents,
    taux_frequence,
    taux_gravite,
)
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(content="Plan de prévention rédigé.", model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""
        return _g()

    async def health(self) -> bool:
        return True


def _inc(idx: str, type_: str, jours: int) -> Incident:
    return Incident(id_externe=idx, date_incident=date(2026, 1, 10), type_incident=type_,
                    gravite="grave" if jours else "mineur", jours_arret=jours)


def test_criticite_et_niveau() -> None:
    assert criticite(Risque(id_externe="R", libelle="x", probabilite=5, gravite=5)) == 25
    assert niveau_criticite(25) == "critique"
    assert niveau_criticite(3) == "faible"
    assert niveau_criticite(12) == "eleve"


def test_cartographie_triee() -> None:
    risques = [
        Risque(id_externe="R1", libelle="Incendie", probabilite=2, gravite=2),   # 4 faible
        Risque(id_externe="R2", libelle="Électrocution", probabilite=5, gravite=4),  # 20 critique
    ]
    carto = cartographie_risques(risques)
    assert carto[0].reference == "R2"
    assert carto[0].niveau == "critique"


def test_statistiques_et_taux() -> None:
    incidents = [
        _inc("I1", "accident_travail", 5),
        _inc("I2", "accident_travail", 0),
        _inc("I3", "presque_accident", 0),
    ]
    stats = statistiques_incidents(incidents)
    assert stats["total"] == 3
    assert stats["nb_avec_arret"] == 1
    assert stats["total_jours_arret"] == 5
    # TF = 1 accident avec arrêt * 1e6 / 100000 h = 10 ; TG = 5*1000/100000 = 0.05
    assert taux_frequence(incidents, heures_travaillees=100000) == Decimal("10.00")
    assert taux_gravite(incidents, heures_travaillees=100000) == Decimal("0.05")


async def test_agent_plan_prevention_priorise(  ) -> None:
    agent = HseAgent(client=_CapturingClient(), settings=Settings())
    carto = cartographie_risques([Risque(id_externe="R2", libelle="Électrocution", probabilite=5, gravite=4)])
    out = await agent.generer_plan_prevention(risques=carto, contexte="atelier")
    assert "rédigé" in out
    assert "Électrocution" in agent._client.last  # type: ignore[attr-defined]


async def test_agent_rapport_durabilite() -> None:
    agent = HseAgent(client=_CapturingClient(), settings=Settings())
    ind = agent.indicateurs([_inc("I1", "accident_travail", 5)], heures_travaillees=100000)
    await agent.generer_rapport_durabilite(indicateurs=ind, periode="2025")
    assert "taux_frequence" in agent._client.last  # type: ignore[attr-defined]
