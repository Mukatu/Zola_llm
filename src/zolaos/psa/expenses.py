"""Notes de frais — référentiel de catégories + synthèse (PSA).

Un frais **facturable** est un débours refacturable au client ; qu'il soit
facturable ou non, un frais (approuvé) est un **coût** du cabinet. Calcul entier
(XAF), les `rejected` exclus.
"""

from __future__ import annotations

from typing import Any

# Catégories de frais (référentiel fermé — alimente le formulaire et le filtrage).
EXPENSE_CATEGORIES: tuple[str, ...] = (
    "transport",
    "hebergement",
    "repas",
    "fournitures",
    "honoraires_tiers",
    "autre",
)

_ACTIVE_STATUSES = ("draft", "submitted", "approved")


def summarize_expenses(items: list[dict[str, Any]], *, currency: str = "XAF") -> dict[str, Any]:
    """Synthèse d'un lot de frais : total, part facturable, part refacturable approuvée
    (prête à porter sur une facture), et ventilation par catégorie. `rejected` exclus."""
    total = billable_total = refacturable_approved = 0
    by_category: dict[str, int] = {}
    count = 0
    for e in items:
        if e.get("status") not in _ACTIVE_STATUSES:
            continue
        count += 1
        amount = int(e.get("amount", 0) or 0)
        billable = bool(e.get("billable", False))
        total += amount
        by_category[e.get("category", "autre")] = (
            by_category.get(e.get("category", "autre"), 0) + amount
        )
        if billable:
            billable_total += amount
            if e.get("status") == "approved":
                refacturable_approved += amount
    return {
        "count": count,
        "total": total,
        "billable_total": billable_total,
        "refacturable_approved": refacturable_approved,  # approuvé + facturable = prêt à refacturer
        "by_category": by_category,
        "currency": currency,
    }
