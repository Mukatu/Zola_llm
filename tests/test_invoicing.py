"""Tests unitaires facturation d'honoraires (zolaos.psa.invoicing).

Couvre les deux helpers purs, sans HTTP ni base :
- next_invoice_number : numérotation séquentielle par année
- aging_bucket : tranche d'ancienneté d'une créance selon les jours de retard
"""

from __future__ import annotations

from zolaos.psa.invoicing import aging_bucket, next_invoice_number


def test_next_invoice_number_first_of_year() -> None:
    assert next_invoice_number(2026, 0) == "FACT-2026-0001"


def test_next_invoice_number_increments_with_count() -> None:
    assert next_invoice_number(2026, 6) == "FACT-2026-0007"


def test_aging_bucket_not_yet_due() -> None:
    assert aging_bucket(-5) == "current"
    assert aging_bucket(0) == "current"


def test_aging_bucket_1_to_30() -> None:
    assert aging_bucket(15) == "1-30"


def test_aging_bucket_31_to_60() -> None:
    assert aging_bucket(45) == "31-60"


def test_aging_bucket_61_to_90() -> None:
    assert aging_bucket(75) == "61-90"


def test_aging_bucket_over_90() -> None:
    assert aging_bucket(120) == "90+"
