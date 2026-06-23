"""Moteur de KPIs déterministe — BI / Pilotage (addendum §3.1, BI-1).

Fonctions **pures** : les indicateurs sont calculés **en code** à partir des
modèles canoniques (Invoice, BankTransaction, Employee) et des sorties paie.
Le LLM ne calcule jamais ces chiffres — il les narre (cf. `agent.py`).
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from zolaos.connectors.models import BankTransaction, Employee, Invoice

_ZERO = Decimal("0")


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class KpiValue(BaseModel):
    """Un indicateur calculé."""

    code: str
    libelle: str
    valeur: Decimal
    unite: str = "XAF"  # XAF | % | jours | unité
    domaine: str = "finance"  # commercial | finance | rh
    periode: str | None = None


# ----------------------------------------------------------------- primitives


def chiffre_affaires(invoices: Iterable[Invoice]) -> Decimal:
    """CA HT = somme des factures de vente (HT)."""
    return sum((i.montant_ht_xaf for i in invoices if i.sens == "vente"), _ZERO)


def chiffre_affaires_ttc(invoices: Iterable[Invoice]) -> Decimal:
    return sum((i.montant_ttc_xaf for i in invoices if i.sens == "vente"), _ZERO)


def achats(invoices: Iterable[Invoice]) -> Decimal:
    """Achats HT = somme des factures d'achat (HT)."""
    return sum((i.montant_ht_xaf for i in invoices if i.sens == "achat"), _ZERO)


def marge_brute(invoices: Iterable[Invoice]) -> Decimal:
    return chiffre_affaires(invoices) - achats(invoices)


def encours_clients(invoices: Iterable[Invoice]) -> Decimal:
    """Encours = factures de vente non payées (TTC)."""
    return sum((i.montant_ttc_xaf for i in invoices if i.sens == "vente" and not i.payee), _ZERO)


def tresorerie_nette(transactions: Iterable[BankTransaction]) -> Decimal:
    """Flux net = crédits − débits sur la période."""
    credit = sum((abs(t.montant_xaf) for t in transactions if t.sens == "credit"), _ZERO)
    debit = sum((abs(t.montant_xaf) for t in transactions if t.sens == "debit"), _ZERO)
    return credit - debit


def effectif(employees: Iterable[Employee]) -> int:
    return sum(1 for e in employees if e.actif)


def masse_salariale(employees: Iterable[Employee]) -> Decimal:
    """Masse salariale brute (somme des salaires de base des actifs)."""
    return sum((e.salaire_base_xaf or _ZERO for e in employees if e.actif), _ZERO)


def dso_jours(invoices: Iterable[Invoice], *, periode_jours: int = 30) -> Decimal:
    """Days Sales Outstanding = encours / CA TTC × jours. 0 si pas de CA."""
    inv = list(invoices)
    ca_ttc = chiffre_affaires_ttc(inv)
    if ca_ttc <= 0:
        return _ZERO
    return (encours_clients(inv) / ca_ttc * Decimal(periode_jours)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )


# ----------------------------------------------------------------- assemblage


def compute_kpis(
    *,
    invoices: list[Invoice] | None = None,
    transactions: list[BankTransaction] | None = None,
    employees: list[Employee] | None = None,
    periode: str | None = None,
    dso_jours_base: int = 30,
) -> list[KpiValue]:
    """Assemble les KPIs calculables selon les données fournies (déterministe)."""
    out: list[KpiValue] = []

    def add(code: str, libelle: str, valeur: Decimal | int, unite: str, domaine: str) -> None:
        out.append(
            KpiValue(
                code=code,
                libelle=libelle,
                valeur=Decimal(valeur),
                unite=unite,
                domaine=domaine,
                periode=periode,
            )
        )

    if invoices is not None:
        add(
            "ca_ht",
            "Chiffre d'affaires (HT)",
            _xaf(chiffre_affaires(invoices)),
            "XAF",
            "commercial",
        )
        add("achats_ht", "Achats (HT)", _xaf(achats(invoices)), "XAF", "commercial")
        add("marge_brute", "Marge brute", _xaf(marge_brute(invoices)), "XAF", "commercial")
        add(
            "encours_clients",
            "Encours clients (TTC)",
            _xaf(encours_clients(invoices)),
            "XAF",
            "finance",
        )
        add(
            "dso",
            "DSO (délai moyen d'encaissement)",
            dso_jours(invoices, periode_jours=dso_jours_base),
            "jours",
            "finance",
        )

    if transactions is not None:
        add(
            "tresorerie_nette",
            "Flux de trésorerie net",
            _xaf(tresorerie_nette(transactions)),
            "XAF",
            "finance",
        )

    if employees is not None:
        add("effectif", "Effectif actif", effectif(employees), "unité", "rh")
        add(
            "masse_salariale",
            "Masse salariale brute",
            _xaf(masse_salariale(employees)),
            "XAF",
            "rh",
        )

    return out
