"""Clôture continue & réconciliation temps réel — compta IA-native.

Au lieu d'attendre la fin du mois, le rapprochement facture ↔ encaissement est
recalculé **en continu** (à chaque nouveau mouvement). 100% **déterministe** :
le lettrage est un calcul exact (montant + fenêtre de date), pas une supposition
du LLM. Le LLM (séparément) ne fait qu'expliquer/alerter.

Sortie : rapprochements, factures en attente (encours), mouvements non lettrés,
taux de lettrage, et un **instantané de clôture continue** (balance vivante).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from zolaos.connectors.models import BankTransaction, Invoice

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Rapprochement:
    invoice_id: str
    transaction_id: str
    montant_xaf: Decimal


@dataclass(frozen=True)
class FactureEnAttente:
    invoice_id: str
    numero: str
    tiers: str
    montant_ttc_xaf: Decimal


@dataclass(frozen=True)
class ClotureContinue:
    total_factures: int
    lettrees: int
    en_attente: int
    taux_lettrage_pct: Decimal
    montant_lettre_xaf: Decimal
    encours_clients_xaf: Decimal


@dataclass(frozen=True)
class ReconciliationReport:
    rapprochements: list[Rapprochement] = field(default_factory=list)
    factures_en_attente: list[FactureEnAttente] = field(default_factory=list)
    mouvements_non_rapproches: list[str] = field(default_factory=list)
    cloture: ClotureContinue | None = None


def _jours(a: date, b: date) -> int:
    return abs((a - b).days)


def reconcilier(
    invoices: list[Invoice],
    transactions: list[BankTransaction],
    *,
    fenetre_jours: int = 5,
) -> ReconciliationReport:
    """Rapproche les factures de vente non payées avec les encaissements (crédits).

    Lettrage déterministe : montant TTC identique + écart de date ≤ fenêtre.
    """
    factures = sorted(
        [i for i in invoices if i.sens == "vente" and not i.payee],
        key=lambda i: i.date_emission,
    )
    credits = [t for t in transactions if t.sens == "credit"]
    used: set[str] = set()

    rapprochements: list[Rapprochement] = []
    en_attente: list[FactureEnAttente] = []
    montant_lettre = _ZERO
    encours = _ZERO

    for inv in factures:
        match = next(
            (
                t
                for t in credits
                if t.id_externe not in used
                and abs(t.montant_xaf) == inv.montant_ttc_xaf
                and _jours(t.date_operation, inv.date_emission) <= fenetre_jours
            ),
            None,
        )
        if match is not None:
            used.add(match.id_externe)
            rapprochements.append(
                Rapprochement(inv.id_externe, match.id_externe, inv.montant_ttc_xaf)
            )
            montant_lettre += inv.montant_ttc_xaf
        else:
            en_attente.append(
                FactureEnAttente(inv.id_externe, inv.numero, inv.tiers, inv.montant_ttc_xaf)
            )
            encours += inv.montant_ttc_xaf

    non_rapproches = [t.id_externe for t in credits if t.id_externe not in used]
    total = len(factures)
    taux = (
        (Decimal(len(rapprochements)) / Decimal(total) * 100).quantize(Decimal("0.1"))
        if total
        else _ZERO
    )

    return ReconciliationReport(
        rapprochements=rapprochements,
        factures_en_attente=en_attente,
        mouvements_non_rapproches=non_rapproches,
        cloture=ClotureContinue(
            total_factures=total,
            lettrees=len(rapprochements),
            en_attente=len(en_attente),
            taux_lettrage_pct=taux,
            montant_lettre_xaf=montant_lettre,
            encours_clients_xaf=encours,
        ),
    )
