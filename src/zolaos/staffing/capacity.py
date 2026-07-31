"""Capacité & charge — calcul déterministe du plan de charge (staffing).

Semaine ouvrée = 5 jours. Capacité hebdo = 5 × heures/jour × 60 minutes. La charge
(`load`) = alloué / capacité ; au-delà de 100 %, **sur-affectation**. Tout en entiers
(minutes) — pas d'à-peu-près sur la planification.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

WEEK_BUSINESS_DAYS = 5


def monday_of(d: date) -> date:
    """Lundi de la semaine de `d` (normalise toute date à sa semaine)."""
    return d - timedelta(days=d.weekday())


def week_capacity_minutes(hours_per_day: float) -> int:
    """Capacité hebdomadaire d'un consultant, en minutes (5 j × heures/jour)."""
    return round(WEEK_BUSINESS_DAYS * hours_per_day * 60)


def load_row(allocated_minutes: int, capacity_minutes: int) -> dict[str, Any]:
    """Ligne de charge : alloué vs capacité → dispo, taux de charge, sur-affectation."""
    load_pct = round(allocated_minutes / capacity_minutes * 100) if capacity_minutes else None
    return {
        "allocated_minutes": allocated_minutes,
        "capacity_minutes": capacity_minutes,
        "available_minutes": max(0, capacity_minutes - allocated_minutes),
        "load_pct": load_pct,
        "over_allocated": allocated_minutes > capacity_minutes,
    }
