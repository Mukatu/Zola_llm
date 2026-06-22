"""Sous-agents du pôle ERP (Phase 4)."""

from __future__ import annotations

from zolaos.agents.erp.achats import (
    AchatsAgent,
    ComparatifLigne,
    OffreFournisseur,
    Supplier,
    SupplierScore,
)
from zolaos.agents.erp.compta import (
    Account,
    ChartOfAccounts,
    ComptaAgent,
    JournalValidator,
    ValidationReport,
)
from zolaos.agents.erp.finance import FinanceAgent
from zolaos.agents.erp.payroll import (
    PayrollCalculator,
    PayrollScale,
    PayrollScaleNotValidated,
    load_payroll_scale,
)
from zolaos.agents.erp.projets_ong import ProjetsOngAgent
from zolaos.agents.erp.rh import RhAgent
from zolaos.agents.erp.supply import (
    BonCommande,
    ReapproSuggestion,
    StockItem,
    SupplyChainAgent,
)

__all__ = [
    "RhAgent",
    "FinanceAgent",
    "ProjetsOngAgent",
    "SupplyChainAgent",
    "StockItem",
    "BonCommande",
    "ReapproSuggestion",
    "AchatsAgent",
    "Supplier",
    "OffreFournisseur",
    "SupplierScore",
    "ComparatifLigne",
    "PayrollCalculator",
    "PayrollScale",
    "PayrollScaleNotValidated",
    "load_payroll_scale",
    "ComptaAgent",
    "ChartOfAccounts",
    "Account",
    "JournalValidator",
    "ValidationReport",
]
