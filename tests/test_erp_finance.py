"""Tests du sous-agent Finance (ERP §4.2).

- Détecteurs déterministes (doublons, dépassements, échéances).
- Agrégats analyse.
- analyze_from_connector via un connecteur factice.
- synthesize : le LLM reçoit les chiffres déjà calculés (narre, ne calcule pas).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from zolaos.agents.erp.finance import FinanceAgent
from zolaos.connectors.base import FinanceConnector, InvoiceConnector
from zolaos.connectors.models import BankTransaction, Invoice
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


def _tx(
    idx: str, montant: str, sens: str, d: date = date(2026, 1, 10), libelle: str = "Paiement"
) -> BankTransaction:
    return BankTransaction(
        id_externe=idx,
        date_operation=d,
        libelle=libelle,
        montant_xaf=Decimal(montant),
        sens=sens,
        canal="bank",
    )


def _inv(idx: str, ttc: str, *, echeance: date | None, payee: bool = False) -> Invoice:
    return Invoice(
        id_externe=idx,
        numero=f"F-{idx}",
        tiers="ACME",
        date_emission=date(2025, 12, 1),
        date_echeance=echeance,
        montant_ht_xaf=Decimal(ttc),
        montant_ttc_xaf=Decimal(ttc),
        payee=payee,
    )


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self, content: str) -> None:
        self._content = content
        self.last_user_msg = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last_user_msg = messages[-1].content
        return GenerationResult(content=self._content, model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield self._content

        return _g()

    async def health(self) -> bool:
        return True


class _FakeFinanceConnector(FinanceConnector, InvoiceConnector):
    name = "fake_fin"

    async def list_bank_transactions(self, **f: Any) -> list[BankTransaction]:
        return [
            _tx("T1", "500000", "credit"),
            _tx("T2", "1500000", "debit"),
            _tx("T3", "200000", "debit", libelle="Loyer"),
            _tx("T4", "200000", "debit", libelle="Loyer"),
        ]

    async def list_invoices(self, **f: Any) -> list[Invoice]:
        return [_inv("I1", "300000", echeance=date(2025, 12, 15))]

    async def read_invoice(self, invoice_id: str) -> Invoice:
        return _inv(invoice_id, "300000", echeance=date(2025, 12, 15))


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def agent(settings: Settings) -> FinanceAgent:
    return FinanceAgent(client=_CapturingClient("Synthèse de trésorerie..."), settings=settings)


def test_detect_duplicates(agent: FinanceAgent) -> None:
    txs = [
        _tx("A", "200000", "debit", libelle="Loyer"),
        _tx("B", "200000", "debit", libelle="Loyer"),
    ]
    found = agent.detect_duplicates(txs)
    assert len(found) == 1
    assert found[0].type == "doublon"
    assert set(found[0].references) == {"A", "B"}


def test_detect_large_outflows(agent: FinanceAgent) -> None:
    txs = [_tx("A", "1500000", "debit"), _tx("B", "100000", "debit"), _tx("C", "5000000", "credit")]
    found = agent.detect_large_outflows(txs, Decimal("1000000"))
    assert [f.references[0] for f in found] == ["A"]  # crédit ignoré, petit débit ignoré
    assert found[0].type == "depassement"


def test_detect_overdue_invoices(agent: FinanceAgent) -> None:
    invs = [
        _inv("I1", "300000", echeance=date(2025, 12, 1)),
        _inv("I2", "100000", echeance=date(2025, 12, 1), payee=True),
        _inv("I3", "100000", echeance=None),
    ]
    found = agent.detect_overdue_invoices(invs, as_of=date(2026, 1, 15))
    assert [f.references[0] for f in found] == ["I1"]  # payée + sans échéance exclues
    assert found[0].severity == "high"  # > 30 jours


def test_analyze_aggregates(agent: FinanceAgent) -> None:
    txs = [_tx("A", "500000", "credit"), _tx("B", "1500000", "debit")]
    res = agent.analyze(txs, large_threshold_xaf=Decimal("1000000"), as_of=date(2026, 1, 15))
    assert res.total_credit_xaf == Decimal("500000")
    assert res.total_debit_xaf == Decimal("1500000")
    assert res.net_xaf == Decimal("-1000000")
    assert any(f.type == "depassement" for f in res.findings)


async def test_analyze_from_connector(settings: Settings) -> None:
    agent = FinanceAgent(
        client=_CapturingClient("x"), settings=settings, connector=_FakeFinanceConnector()
    )
    res = await agent.analyze_from_connector(
        large_threshold_xaf=Decimal("1000000"), as_of=date(2026, 1, 15)
    )
    assert res.n_transactions == 4
    types = {f.type for f in res.findings}
    assert {"doublon", "depassement", "echeance"} <= types  # les 3 familles détectées


async def test_synthesize_passes_computed_numbers_to_llm(agent: FinanceAgent) -> None:
    res = agent.analyze([_tx("A", "500000", "credit")], as_of=date(2026, 1, 15))
    out = await agent.synthesize(res, period_label="mensuel")
    assert "Synthèse de trésorerie" in out
    # Le LLM reçoit les chiffres déjà calculés (il narre, ne calcule pas)
    assert "Total crédits : 500000 XAF" in agent._client.last_user_msg  # type: ignore[attr-defined]
