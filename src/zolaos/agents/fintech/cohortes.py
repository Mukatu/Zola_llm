"""Analyse par cohortes (millésimes) — **déterministe**.

Regroupe les prêts **décaissés** par mois de décaissement (millésime YYYY-MM) et
suit leur performance : montant décaissé, remboursé, encours restant, impayés,
taux de remboursement (collecté / dû échu) et PAR30 de la cohorte. Aide à repérer
si la qualité se dégrade selon la génération d'octroi.

Ne portent une cohorte que les prêts effectivement décaissés (date_decaissement
renseignée) : c'est la sémantique « vintage » de la microfinance.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel

_ZERO = Decimal("0")
_Q = Decimal("1")
_CENT = Decimal("100")


class CohortStat(BaseModel):
    periode: str  # millésime YYYY-MM
    nb_prets: int
    montant_decaisse_xaf: Decimal
    montant_du_echu_xaf: Decimal
    montant_rembourse_xaf: Decimal
    encours_restant_xaf: Decimal
    montant_en_retard_xaf: Decimal
    taux_remboursement_pct: Decimal
    par30_pct: Decimal


def _q0(v: Decimal) -> Decimal:
    return v.quantize(_Q, rounding=ROUND_HALF_UP)


def _pct(part: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return _ZERO
    return (part / total * _CENT).quantize(_Q, rounding=ROUND_HALF_UP)


def cohortes(apps: Sequence[Any], installments: Sequence[Any], as_of: Any) -> list[CohortStat]:
    """Construit les cohortes par mois de décaissement (déterministe)."""
    inst_by_app: dict[str, list[Any]] = {}
    for e in installments:
        inst_by_app.setdefault(e.application_id, []).append(e)

    # Regroupe les prêts décaissés par millésime.
    groups: dict[str, list[Any]] = {}
    for a in apps:
        if a.statut != "decaissee" or a.date_decaissement is None:
            continue
        periode = a.date_decaissement.strftime("%Y-%m")
        groups.setdefault(periode, []).append(a)

    out: list[CohortStat] = []
    for periode in sorted(groups):
        prets = groups[periode]
        montant_decaisse = sum((a.montant_demande_xaf for a in prets), _ZERO)
        du_echu = _ZERO
        rembourse = _ZERO
        encours = _ZERO
        en_retard = _ZERO
        at_risk30 = _ZERO
        for a in prets:
            lignes = inst_by_app.get(a.id, [])
            reste_pret = sum(((e.montant_xaf - e.montant_paye_xaf) for e in lignes), _ZERO)
            encours += reste_pret
            rembourse += sum((e.montant_paye_xaf for e in lignes), _ZERO)
            pire_retard = 0
            for e in lignes:
                if e.date_echeance <= as_of:
                    du_echu += e.montant_xaf
                reste = e.montant_xaf - e.montant_paye_xaf
                if e.statut != "paye" and reste > 0 and e.date_echeance < as_of:
                    en_retard += reste
                    pire_retard = max(pire_retard, (as_of - e.date_echeance).days)
            if pire_retard > 30:
                at_risk30 += reste_pret

        out.append(
            CohortStat(
                periode=periode,
                nb_prets=len(prets),
                montant_decaisse_xaf=_q0(montant_decaisse),
                montant_du_echu_xaf=_q0(du_echu),
                montant_rembourse_xaf=_q0(rembourse),
                encours_restant_xaf=_q0(encours),
                montant_en_retard_xaf=_q0(en_retard),
                taux_remboursement_pct=_pct(rembourse, du_echu),
                par30_pct=_pct(at_risk30, encours),
            )
        )
    return out
