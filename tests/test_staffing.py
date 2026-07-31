"""Tests unitaires zolaos.staffing.capacity (fonctions pures — capacité/charge).

Couvre :
- monday_of : normalisation d'une date quelconque au lundi de sa semaine
- week_capacity_minutes : capacité hebdo = 5 jours × heures/jour × 60
- load_row : taux de charge, disponibilité, sur-affectation (dont capacité nulle)
"""

from __future__ import annotations

from datetime import date

from zolaos.staffing.capacity import load_row, monday_of, week_capacity_minutes


def test_monday_of_a_monday_is_itself() -> None:
    monday = date(2026, 7, 27)
    assert monday_of(monday) == monday


def test_monday_of_a_friday() -> None:
    assert monday_of(date(2026, 7, 31)) == date(2026, 7, 27)


def test_monday_of_a_sunday() -> None:
    # Dimanche 2026-08-02 appartient à la semaine du lundi 2026-07-27.
    assert monday_of(date(2026, 8, 2)) == date(2026, 7, 27)


def test_week_capacity_minutes_eight_hours_a_day() -> None:
    assert week_capacity_minutes(8.0) == 2400


def test_load_row_over_allocated() -> None:
    row = load_row(3000, 2400)
    assert row["load_pct"] == 125
    assert row["over_allocated"] is True
    assert row["available_minutes"] == 0


def test_load_row_under_allocated() -> None:
    row = load_row(1200, 2400)
    assert row["load_pct"] == 50
    assert row["over_allocated"] is False
    assert row["available_minutes"] == 1200


def test_load_row_zero_capacity() -> None:
    row = load_row(100, 0)
    assert row["load_pct"] is None
    assert row["over_allocated"] is True
    assert row["available_minutes"] == 0
