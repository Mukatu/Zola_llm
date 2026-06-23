"""Tests Achats / Procurement (ERP, OPS-2) — moteur déterministe + agent."""

from __future__ import annotations

from decimal import Decimal

from zolaos.agents.erp.achats import (
    AchatsAgent,
    OffreFournisseur,
    Supplier,
    comparer_offres,
    score_fournisseur,
    verifier_conformite,
)
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(
            content="Contrat OHADA rédigé.", model="fake", provider=self.provider
        )

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


def _offre(idx: str, fourn: str, ttc: str, delai: int) -> OffreFournisseur:
    return OffreFournisseur(
        id_externe=idx,
        fournisseur=fourn,
        objet="Consommables",
        montant_ht_xaf=Decimal(ttc),
        montant_ttc_xaf=Decimal(ttc),
        delai_livraison_jours=delai,
    )


def test_verifier_conformite() -> None:
    s = Supplier(id_externe="F1", nom="Alpha", documents_conformite=["rccm", "niu"])
    assert verifier_conformite(s) == ["attestation_fiscale"]
    s2 = Supplier(
        id_externe="F2", nom="Beta", documents_conformite=["rccm", "niu", "attestation_fiscale"]
    )
    assert verifier_conformite(s2) == []


def test_score_fournisseur() -> None:
    bon = Supplier(
        id_externe="F1",
        nom="Alpha",
        note_qualite=Decimal("5"),
        delai_moyen_jours=0,
        documents_conformite=["rccm", "niu", "attestation_fiscale"],
    )
    mauvais = Supplier(
        id_externe="F2",
        nom="Beta",
        note_qualite=Decimal("1"),
        delai_moyen_jours=30,
        documents_conformite=[],
    )
    assert score_fournisseur(bon).score > score_fournisseur(mauvais).score
    assert score_fournisseur(bon).grade == "A"


def test_comparer_offres_classe_par_prix_et_delai() -> None:
    offres = [
        _offre("O1", "Alpha", "1000000", 10),  # cher, lent
        _offre("O2", "Beta", "800000", 5),  # moins cher, plus rapide → meilleur
        _offre("O3", "Gamma", "900000", 7),
    ]
    classement = comparer_offres(offres)
    assert classement[0].fournisseur == "Beta"
    assert classement[0].rang == 1
    assert [c.rang for c in classement] == [1, 2, 3]


async def test_agent_redige_contrat_sans_inventer_montant() -> None:
    agent = AchatsAgent(client=_CapturingClient(), settings=Settings())
    out = await agent.rediger_contrat(
        fournisseur="Beta", objet="Fourniture de gants", montant_xaf="800000"
    )
    assert "rédigé" in out
    assert "Beta" in agent._client.last  # type: ignore[attr-defined]
    assert "800000" in agent._client.last  # type: ignore[attr-defined]


async def test_agent_synthese_comparatif() -> None:
    agent = AchatsAgent(client=_CapturingClient(), settings=Settings())
    classement = comparer_offres(
        [_offre("O1", "Beta", "800000", 5), _offre("O2", "Alpha", "1000000", 10)]
    )
    await agent.synthese_comparatif(classement)
    assert "Beta" in agent._client.last  # type: ignore[attr-defined]
    assert "Rang 1" in agent._client.last  # type: ignore[attr-defined]
