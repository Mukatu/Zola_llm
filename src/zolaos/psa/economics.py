"""Économie de la mission & taux d'occupation — calcul déterministe (PSA).

Tout est en **entiers** (minutes, XAF sans sous-unité) : pas d'à-peu-près sur les
chiffres. Les entrées `rejected` sont exclues de tout calcul (temps refusé = néant).
"""

from __future__ import annotations

from typing import Any

_ACTIVE_STATUSES = ("draft", "submitted", "approved")


def entry_amounts(
    *, minutes: int, bill_rate: int, cost_rate: int, billable: bool
) -> dict[str, int]:
    """Montants d'une saisie : honoraires (0 si non facturable) et coût (toujours)."""
    honoraires = round(minutes * bill_rate / 60) if billable else 0
    cost = round(minutes * cost_rate / 60)
    return {"honoraires": honoraires, "cost": cost}


def compute_engagement_economics(
    entries: list[dict[str, Any]], *, currency: str = "XAF"
) -> dict[str, Any]:
    """Agrège l'économie d'une mission à partir de ses feuilles de temps.

    `entries` : dicts `{minutes, bill_rate, cost_rate, billable, status}`. Retourne
    temps (total/facturable), honoraires (total + `wip` = part approuvée, prête à
    facturer), coût, marge et taux de marge. Les `rejected` sont ignorés."""
    minutes = billable_minutes = honoraires = honoraires_wip = cost = 0
    counted = 0
    for e in entries:
        if e.get("status") not in _ACTIVE_STATUSES:
            continue
        counted += 1
        m = int(e.get("minutes", 0) or 0)
        billable = bool(e.get("billable", False))
        amt = entry_amounts(
            minutes=m,
            bill_rate=int(e.get("bill_rate", 0) or 0),
            cost_rate=int(e.get("cost_rate", 0) or 0),
            billable=billable,
        )
        minutes += m
        cost += amt["cost"]
        honoraires += amt["honoraires"]
        if billable:
            billable_minutes += m
        if billable and e.get("status") == "approved":
            honoraires_wip += amt["honoraires"]

    margin = honoraires - cost
    margin_pct = round(margin / honoraires * 100) if honoraires else None
    return {
        "entries": counted,
        "minutes": minutes,
        "hours": round(minutes / 60, 2),
        "billable_minutes": billable_minutes,
        "billable_hours": round(billable_minutes / 60, 2),
        "honoraires": honoraires,
        "honoraires_wip": honoraires_wip,  # approuvé, prêt à facturer (encours)
        "cost": cost,
        "margin": margin,
        "margin_pct": margin_pct,
        "currency": currency,
    }


def compute_utilization(
    *, worked_minutes: int, billable_minutes: int, available_minutes: int
) -> dict[str, Any]:
    """Taux d'occupation (facturable) et d'activité (travaillé) sur une capacité.

    `available_minutes` : capacité de la période (jours ouvrés × heures/jour × 60).
    Taux bornés/None si capacité nulle (évite la division par zéro)."""
    occupation = round(billable_minutes / available_minutes * 100) if available_minutes else None
    activity = round(worked_minutes / available_minutes * 100) if available_minutes else None
    return {
        "worked_minutes": worked_minutes,
        "billable_minutes": billable_minutes,
        "available_minutes": available_minutes,
        "occupation_pct": occupation,  # taux d'occupation (facturable / capacité)
        "activity_pct": activity,  # taux d'activité (travaillé / capacité)
    }
