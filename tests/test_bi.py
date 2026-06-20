"""Tests BI / Pilotage (addendum §3.1).

- KPIs déterministes exacts.
- compute_kpis : codes attendus selon les données.
- BIAgent : synthèse + Q&A reçoivent les chiffres calculés (le LLM ne calcule pas).
- compute_from_connector via connecteur factice.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from zolaos.agents.bi.agent import BIAgent
from zolaos.agents.bi.kpi import (
    chiffre_affaires,
    compute_kpis,
    dso_jours,
    marge_brute,
    masse_salariale,
    tresorerie_nette,
)
from zolaos.connectors.base import FinanceConnector, HRConnector, InvoiceConnector
from zolaos.connectors.models import BankTransaction, Employee, Invoice
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


def _inv(ht: str, ttc: str, *, sens: str = "vente", payee: bool = False) -> Invoice:
    return Invoice(
        id_externe=f"{sens}-{ht}", numero=f"F{ht}", sens=sens, tiers="X",
        date_emission=date(2026, 1, 1), montant_ht_xaf=Decimal(ht),
        montant_ttc_xaf=Decimal(ttc), payee=payee,
    )


def _tx(montant: str, sens: str) -> BankTransaction:
    return BankTransaction(
        id_externe=f"{sens}{montant}", date_operation=date(2026, 1, 5),
        libelle="op", montant_xaf=Decimal(montant), sens=sens, canal="bank",
    )


def _emp(sal: str, actif: bool = True) -> Employee:
    return Employee(id_externe=sal, nom_complet="N", salaire_base_xaf=Decimal(sal), actif=actif)


INVOICES = [_inv("1000", "1180"), _inv("2000", "2360", payee=True), _inv("500", "590", sens="achat")]
TRANSACTIONS = [_tx("5000", "credit"), _tx("2000", "debit")]
EMPLOYEES = [_emp("300000"), _emp("500000"), _emp("999", actif=False)]


class _CapturingClient(LLMClient):
    provider = "fake"

    def __init__(self) -> None:
        self.last = ""

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        self.last = messages[-1].content
        return GenerationResult(content="Synthèse de pilotage.", model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""
        return _g()

    async def health(self) -> bool:
        return True


class _FakeAllConnector(HRConnector, InvoiceConnector, FinanceConnector):
    name = "fake_all"

    async def list_invoices(self, **f: Any) -> list[Invoice]:
        return INVOICES

    async def read_invoice(self, invoice_id: str) -> Invoice:
        return INVOICES[0]

    async def list_bank_transactions(self, **f: Any) -> list[BankTransaction]:
        return TRANSACTIONS

    async def list_employees(self, **f: Any) -> list[Employee]:
        return EMPLOYEES


# ------------------------------------------------- KPIs déterministes

def test_kpi_primitives() -> None:
    assert chiffre_affaires(INVOICES) == Decimal("3000")
    assert marge_brute(INVOICES) == Decimal("2500")           # 3000 - 500
    assert tresorerie_nette(TRANSACTIONS) == Decimal("3000")  # 5000 - 2000
    assert masse_salariale(EMPLOYEES) == Decimal("800000")    # inactif exclu
    assert dso_jours(INVOICES, periode_jours=30) == Decimal("10")  # 1180/3540*30


def test_compute_kpis_codes() -> None:
    kpis = compute_kpis(invoices=INVOICES, transactions=TRANSACTIONS, employees=EMPLOYEES, periode="2026-01")
    codes = {k.code: k.valeur for k in kpis}
    assert codes["ca_ht"] == Decimal("3000")
    assert codes["effectif"] == Decimal("2")
    assert codes["tresorerie_nette"] == Decimal("3000")
    assert {"ca_ht", "marge_brute", "encours_clients", "dso", "tresorerie_nette", "effectif", "masse_salariale"} <= set(codes)


def test_compute_kpis_partial_data() -> None:
    # Seulement RH fourni → seuls les KPIs RH
    kpis = compute_kpis(employees=EMPLOYEES)
    assert {k.code for k in kpis} == {"effectif", "masse_salariale"}


# ------------------------------------------------- agent BI

async def test_synthesize_passes_numbers_to_llm() -> None:
    agent = BIAgent(client=_CapturingClient(), settings=Settings())
    kpis = compute_kpis(invoices=INVOICES, periode="2026-01")
    out = await agent.synthesize(kpis, periode="2026-01")
    assert "Synthèse de pilotage" in out
    assert "Chiffre d'affaires" in agent._client.last  # type: ignore[attr-defined]
    assert "3000" in agent._client.last  # type: ignore[attr-defined]


async def test_answer_uses_kpi_set() -> None:
    agent = BIAgent(client=_CapturingClient(), settings=Settings())
    kpis = compute_kpis(employees=EMPLOYEES)
    await agent.answer("Quel est l'effectif ?", kpis)
    assert "Effectif actif" in agent._client.last  # type: ignore[attr-defined]
    assert "Question" in agent._client.last  # type: ignore[attr-defined]


async def test_compute_from_connector() -> None:
    agent = BIAgent(client=_CapturingClient(), settings=Settings(), connector=_FakeAllConnector())
    kpis = await agent.compute_from_connector(periode="2026-01")
    codes = {k.code for k in kpis}
    assert {"ca_ht", "tresorerie_nette", "effectif"} <= codes
