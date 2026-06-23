"""Tests Moyens Généraux / Facility (ERP, OPS-3) — moteur déterministe + agent."""

from __future__ import annotations

from datetime import date

from zolaos.agents.erp.facility import (
    Asset,
    Echeance,
    FacilityAgent,
    echeances_dues,
    maintenances_dues,
    prochaine_maintenance,
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
        return GenerationResult(
            content="Ordre de travail rédigé.", model="fake", provider=self.provider
        )

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


def test_prochaine_maintenance() -> None:
    a = Asset(
        id_externe="V1",
        libelle="Camion",
        type_actif="vehicule",
        maintenance_intervalle_jours=90,
        derniere_maintenance=date(2026, 1, 1),
    )
    assert prochaine_maintenance(a) == date(2026, 4, 1)
    # Pas planifiable sans intervalle/dernière
    assert prochaine_maintenance(Asset(id_externe="X", libelle="Y")) is None


def test_maintenances_dues_retard_et_horizon() -> None:
    assets = [
        Asset(
            id_externe="V1",
            libelle="Camion",
            maintenance_intervalle_jours=20,
            derniere_maintenance=date(2026, 1, 1),
        ),  # due 2026-01-21 → -11 j (retard)
        Asset(
            id_externe="G1",
            libelle="Groupe",
            maintenance_intervalle_jours=200,
            derniere_maintenance=date(2026, 1, 1),
        ),  # due 2026-07-20 → hors horizon
    ]
    alertes = maintenances_dues(assets, as_of=AS_OF, horizon_jours=30)
    assert [a.reference for a in alertes] == ["V1"]
    assert alertes[0].jours_restants < 0
    assert alertes[0].urgence == "high"


def test_echeances_dues() -> None:
    echeances = [
        Echeance(
            id_externe="E1",
            type_echeance="assurance",
            libelle="Assurance flotte",
            date_echeance=date(2026, 2, 10),
        ),  # +9 j
        Echeance(
            id_externe="E2",
            type_echeance="visite_technique",
            libelle="VT camion",
            date_echeance=date(2026, 1, 25),
        ),  # -7 j retard
        Echeance(
            id_externe="E3",
            type_echeance="licence",
            libelle="Licence logiciel",
            date_echeance=date(2026, 6, 1),
        ),  # hors horizon
    ]
    refs = {a.reference for a in echeances_dues(echeances, as_of=AS_OF, horizon_jours=30)}
    assert refs == {"E1", "E2"}


async def test_agent_ordre_travail_sans_inventer_date() -> None:
    agent = FacilityAgent(client=_CapturingClient(), settings=Settings())
    assets = [
        Asset(
            id_externe="V1",
            libelle="Camion",
            maintenance_intervalle_jours=20,
            derniere_maintenance=date(2026, 1, 1),
        )
    ]
    alerte = maintenances_dues(assets, as_of=AS_OF, horizon_jours=30)[0]
    out = await agent.rediger_ordre_travail(alerte)
    assert "rédigé" in out
    assert "Camion" in agent._client.last  # type: ignore[attr-defined]
    assert str(alerte.date_cible) in agent._client.last  # type: ignore[attr-defined]
