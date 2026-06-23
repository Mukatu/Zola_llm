"""Tests Supply Chain & Stocks (ERP, OPS-1) — moteur déterministe + agent."""

from __future__ import annotations

from decimal import Decimal

from zolaos.agents.erp.supply import (
    StockItem,
    SupplyChainAgent,
    analyser_reappro,
    generer_bon_commande,
    jours_avant_rupture,
    point_de_commande,
)
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


def _item(
    sku: str,
    q: str,
    *,
    conso: str = "0",
    delai: int = 0,
    secu: str = "0",
    seuil: str | None = None,
    qte_reappro: str | None = None,
) -> StockItem:
    return StockItem(
        sku=sku,
        libelle=f"Art {sku}",
        quantite_actuelle=Decimal(q),
        conso_moyenne_jour=Decimal(conso),
        delai_appro_jours=delai,
        stock_securite=Decimal(secu),
        seuil_reappro=Decimal(seuil) if seuil else None,
        quantite_reappro=Decimal(qte_reappro) if qte_reappro else None,
    )


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(
            content="Bon de commande rédigé.", model="fake", provider=self.provider
        )

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


def test_point_de_commande_calcule_et_seuil() -> None:
    assert point_de_commande(_item("A", "10", conso="2", delai=5, secu="4")) == Decimal("14")
    assert point_de_commande(_item("C", "40", seuil="50")) == Decimal("50")  # seuil explicite


def test_jours_avant_rupture() -> None:
    assert jours_avant_rupture(_item("A", "10", conso="2")) == Decimal("5.0")
    assert jours_avant_rupture(_item("Z", "10", conso="0")) is None  # pas de conso


def test_analyser_reappro_urgence() -> None:
    items = [
        _item(
            "A", "10", conso="2", delai=5, secu="4"
        ),  # point 14, stock 10 → suggestion, rupture 5j ≤ délai 5 → high
        _item("B", "100", conso="1", delai=3),  # point 3, stock 100 → pas de suggestion
        _item("C", "40", seuil="50"),  # point 50, stock 40, conso 0 → suggestion medium
    ]
    sug = {s.sku: s for s in analyser_reappro(items)}
    assert set(sug) == {"A", "C"}
    assert sug["A"].urgence == "high"
    assert sug["C"].urgence == "medium"
    assert sug["A"].quantite_a_commander == Decimal("18")  # 14*2 - 10


def test_generer_bon_commande() -> None:
    items = [_item("A", "10", conso="2", delai=5, secu="4"), _item("C", "40", seuil="50")]
    bc = generer_bon_commande(analyser_reappro(items), fournisseur="MedDistrib")
    assert bc.fournisseur == "MedDistrib"
    assert {l.sku for l in bc.lignes} == {"A", "C"}


async def test_agent_redige_bon_commande_sans_inventer() -> None:
    agent = SupplyChainAgent(client=_CapturingClient(), settings=Settings())
    items = [_item("A", "10", conso="2", delai=5, secu="4")]
    bc = agent.bon_commande(analyser_reappro(items))
    out = await agent.rediger_bon_commande(bc)
    assert "rédigé" in out
    assert "SKU A" in agent._client.last  # type: ignore[attr-defined]
    assert "18" in agent._client.last  # quantité calculée transmise  # type: ignore[attr-defined]


def test_module_in_personalization_catalogue() -> None:
    from zolaos.core.personalization import all_module_codes

    assert "erp.supply_chain" in all_module_codes()
