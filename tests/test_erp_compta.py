"""Tests Compta & Fiscalité (ERP §4.3) — moteur hybride.

- Plan de comptes : chargement, résolution exacte + sous-comptes, inconnu.
- Validation déterministe : équilibre, comptes inconnus, partie double, sens.
- ComptaAgent : instanciation + marqueurs prompt + validate_entry délégué.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from zolaos.agents.erp.compta import ChartOfAccounts, ComptaAgent, JournalValidator
from zolaos.agents.rag_agent import RAGAgent
from zolaos.connectors.models import JournalEntry, JournalLine
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


class _FakeClient(LLMClient):
    provider = "fake"

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        return GenerationResult(content="", model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        async def _g():
            yield ""

        return _g()

    async def health(self) -> bool:
        return True


@pytest.fixture
def chart() -> ChartOfAccounts:
    return ChartOfAccounts.load("cg")


def _entry(lignes: list[JournalLine]) -> JournalEntry:
    return JournalEntry(date_ecriture=date(2026, 1, 5), journal="VT", libelle="Test", lignes=lignes)


# ----------------------------------------------------- plan de comptes


def test_chart_load_and_resolve(chart: ChartOfAccounts) -> None:
    assert chart.validated is False  # seed non validé
    assert chart.get("411").libelle == "Clients"
    assert chart.resolve("4011").numero == "401"  # sous-compte → parent
    assert chart.resolve("99999") is None  # hors plan


# ----------------------------------------------------- validation


def test_valid_balanced_entry(chart: ChartOfAccounts) -> None:
    rep = JournalValidator(chart).validate(
        _entry(
            [
                JournalLine(compte="411", libelle="Client", debit_xaf=Decimal("1180")),
                JournalLine(compte="701", libelle="Vente", credit_xaf=Decimal("1000")),
                JournalLine(compte="4431", libelle="TVA collectée", credit_xaf=Decimal("180")),
            ]
        )
    )
    assert rep.ok
    assert rep.errors == []
    assert rep.total_debit_xaf == rep.total_credit_xaf == Decimal("1180")


def test_unbalanced_entry_rejected(chart: ChartOfAccounts) -> None:
    rep = JournalValidator(chart).validate(
        _entry(
            [
                JournalLine(compte="411", libelle="Client", debit_xaf=Decimal("1180")),
                JournalLine(compte="701", libelle="Vente", credit_xaf=Decimal("900")),
            ]
        )
    )
    assert not rep.ok
    assert any("déséquilibrée" in e for e in rep.errors)


def test_unknown_account_rejected(chart: ChartOfAccounts) -> None:
    rep = JournalValidator(chart).validate(
        _entry(
            [
                JournalLine(compte="999", libelle="???", debit_xaf=Decimal("100")),
                JournalLine(compte="701", libelle="Vente", credit_xaf=Decimal("100")),
            ]
        )
    )
    assert not rep.ok
    assert any("inconnu" in e.lower() for e in rep.errors)


def test_single_line_rejected(chart: ChartOfAccounts) -> None:
    rep = JournalValidator(chart).validate(
        _entry(
            [
                JournalLine(compte="411", libelle="Client", debit_xaf=Decimal("100")),
            ]
        )
    )
    assert not rep.ok


def test_unusual_sens_is_warning_not_error(chart: ChartOfAccounts) -> None:
    # Débit sur 701 (normalement créditeur) + crédit sur 411 (normalement débiteur)
    rep = JournalValidator(chart).validate(
        _entry(
            [
                JournalLine(compte="701", libelle="Annulation vente", debit_xaf=Decimal("500")),
                JournalLine(compte="411", libelle="Client", credit_xaf=Decimal("500")),
            ]
        )
    )
    assert rep.ok  # équilibré + comptes connus → valide
    assert rep.warnings  # mais mouvements inhabituels signalés


# ----------------------------------------------------- agent


def test_compta_agent_instantiates_and_prompt() -> None:
    agent = ComptaAgent(client=_FakeClient(), settings=Settings())
    assert issubclass(ComptaAgent, RAGAgent)
    prompt = agent._system_prompt.lower()
    for marker in ("syscohada", "audcif", "tva", "expert-comptable"):
        assert marker in prompt, f"marqueur manquant: {marker}"


def test_compta_agent_validate_entry_delegates() -> None:
    agent = ComptaAgent(client=_FakeClient(), settings=Settings())
    rep = agent.validate_entry(
        _entry(
            [
                JournalLine(compte="601", libelle="Achat", debit_xaf=Decimal("1000")),
                JournalLine(compte="401", libelle="Fournisseur", credit_xaf=Decimal("1000")),
            ]
        )
    )
    assert rep.ok
