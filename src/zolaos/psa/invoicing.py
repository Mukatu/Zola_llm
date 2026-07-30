"""Facturation d'honoraires — utilitaires purs (numérotation, échéancier).

La logique DB (regrouper les temps, émettre, encaisser) vit dans l'endpoint ; ici,
les fonctions déterministes et testables sans base : numéro de facture et âge de
créance (base des relances).
"""

from __future__ import annotations


def next_invoice_number(year: int, count_this_year: int) -> str:
    """Numéro séquentiel lisible : ``FACT-2026-0007`` (count = factures déjà émises l'année)."""
    return f"FACT-{year:04d}-{count_this_year + 1:04d}"


# Tranches d'âge de créance (échéancier / relances). `days_overdue` négatif = à échoir.
AGING_BUCKETS: tuple[str, ...] = ("current", "1-30", "31-60", "61-90", "90+")


def aging_bucket(days_overdue: int) -> str:
    """Tranche d'ancienneté d'une créance selon les jours de retard (échéance dépassée)."""
    if days_overdue <= 0:
        return "current"  # à échoir (pas encore due)
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"
