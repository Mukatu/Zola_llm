"""Tests unitaires PSA — notes de frais (zolaos.psa.expenses).

Aucun HTTP, aucune DB : calcul déterministe pur.
"""

from __future__ import annotations

from zolaos.psa.expenses import EXPENSE_CATEGORIES, summarize_expenses

# ----------------------------------------------------------------------------
# EXPENSE_CATEGORIES
# ----------------------------------------------------------------------------


def test_expense_categories_are_the_expected_closed_set():
    assert EXPENSE_CATEGORIES == (
        "transport",
        "hebergement",
        "repas",
        "fournitures",
        "honoraires_tiers",
        "autre",
    )


# ----------------------------------------------------------------------------
# summarize_expenses
# ----------------------------------------------------------------------------


def test_summarize_expenses_mix_and_rejected_excluded():
    items = [
        # facturable, approuvé : compte partout
        {"amount": 50000, "billable": True, "status": "approved", "category": "transport"},
        # non facturable, approuvé : coût uniquement
        {"amount": 30000, "billable": False, "status": "approved", "category": "repas"},
        # facturable mais rejeté : DOIT être ignoré intégralement
        {"amount": 99999, "billable": True, "status": "rejected", "category": "autre"},
    ]
    summary = summarize_expenses(items)

    assert summary["count"] == 2  # le rejeté n'est pas compté
    assert summary["total"] == 80000  # 50000 + 30000, le rejeté exclu
    assert summary["billable_total"] == 50000
    assert summary["refacturable_approved"] == 50000
    assert summary["by_category"] == {"transport": 50000, "repas": 30000}
    assert summary["currency"] == "XAF"


def test_summarize_expenses_billable_but_not_yet_approved_excluded_from_refacturable():
    items = [
        {"amount": 40000, "billable": True, "status": "submitted", "category": "transport"},
    ]
    summary = summarize_expenses(items)
    assert summary["count"] == 1
    assert summary["total"] == 40000
    assert summary["billable_total"] == 40000
    # facturable mais pas encore approuvé : pas prêt à refacturer
    assert summary["refacturable_approved"] == 0


def test_summarize_expenses_empty_list():
    summary = summarize_expenses([])
    assert summary["count"] == 0
    assert summary["total"] == 0
    assert summary["billable_total"] == 0
    assert summary["refacturable_approved"] == 0
    assert summary["by_category"] == {}
    assert summary["currency"] == "XAF"


def test_summarize_expenses_custom_currency():
    items = [
        {"amount": 1000, "billable": False, "status": "draft", "category": "fournitures"},
    ]
    summary = summarize_expenses(items, currency="EUR")
    assert summary["currency"] == "EUR"
    assert summary["total"] == 1000
