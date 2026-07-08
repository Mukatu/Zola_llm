"""Amortissement d'un prêt — génération **déterministe** d'un échéancier.

Annuités constantes (mensualité fixe), ventilation principal / intérêts par
échéance ; la dernière échéance solde le capital restant (évite les résidus
d'arrondi). Taux **indicatif paramétrable** (aucun taux d'usure affirmé).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

_ZERO = Decimal("0")
_SOU = Decimal("0.01")


def _q2(v: Decimal) -> Decimal:
    return v.quantize(_SOU, rounding=ROUND_HALF_UP)


def add_months(d: date, n: int) -> date:
    """Décale une date de n mois (clamp du jour en fin de mois)."""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    days_in = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
               31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, days_in))


def monthly_payment(principal: Decimal, taux_mensuel: Decimal, n: int) -> Decimal:
    """Mensualité d'un amortissement à annuités constantes."""
    if principal <= 0 or n <= 0:
        return _ZERO
    if taux_mensuel <= 0:
        return _q2(principal / Decimal(n))
    facteur = (Decimal(1) + taux_mensuel) ** n
    return _q2(principal * taux_mensuel * facteur / (facteur - Decimal(1)))


class Echeance(BaseModel):
    numero: int
    date_echeance: date
    principal_xaf: Decimal
    interet_xaf: Decimal
    montant_xaf: Decimal


def build_schedule(
    montant: Decimal, taux_annuel: Decimal, duree_mois: int, date_debut: date
) -> list[Echeance]:
    """Construit l'échéancier (première échéance à date_debut + 1 mois)."""
    taux_m = (taux_annuel / Decimal("12")).quantize(Decimal("0.000001"))
    mensualite = monthly_payment(montant, taux_m, duree_mois)
    solde = montant
    out: list[Echeance] = []
    for i in range(1, duree_mois + 1):
        interet = _q2(solde * taux_m)
        if i == duree_mois:
            principal = solde  # solde le capital restant
            total = _q2(principal + interet)
        else:
            principal = _q2(mensualite - interet)
            total = mensualite
        solde = _q2(solde - principal)
        out.append(
            Echeance(
                numero=i,
                date_echeance=add_months(date_debut, i),
                principal_xaf=principal,
                interet_xaf=interet,
                montant_xaf=total,
            )
        )
    return out
