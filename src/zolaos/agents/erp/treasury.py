"""Trésorerie — moteur déterministe (position de caisse, consolidation).

**Aucun LLM** : la position de trésorerie est calculée en code (norme SYSCOHADA
classe 5). Position réalisée = solde initial + flux **réalisés** ; position
projetée = position réalisée + flux **prévus** (à venir).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")

# Au-delà de ce montant, un décaissement requiert une double validation (N1 puis N2).
SEUIL_DECAISSEMENT_DEFAUT_XAF = Decimal("1000000")


class CompteTresorerie(BaseModel):
    model_config = {"extra": "forbid"}

    code: str
    libelle: str = ""
    type: str = "banque"  # banque | caisse | mobile_money
    devise: str = "XAF"
    solde_initial_xaf: Decimal = Field(default=_ZERO)


class FluxTresorerie(BaseModel):
    model_config = {"extra": "forbid"}

    compte_code: str
    sens: str  # encaissement | decaissement
    montant_xaf: Decimal = Field(default=_ZERO)
    statut: str = "realise"  # prevu | realise


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CompteLigne:
    code: str
    libelle: str
    type: str
    devise: str
    solde_initial_xaf: Decimal
    encaisse_xaf: Decimal
    decaisse_xaf: Decimal
    solde_realise_xaf: Decimal
    encaisse_prevu_xaf: Decimal
    decaisse_prevu_xaf: Decimal
    solde_projete_xaf: Decimal


@dataclass(frozen=True)
class PositionTresorerie:
    nb_comptes: int
    total_realise_xaf: Decimal
    total_projete_xaf: Decimal
    par_devise: dict[str, str]  # devise -> solde réalisé (str)
    par_compte: list[CompteLigne] = field(default_factory=list)


def position_tresorerie(
    comptes: list[CompteTresorerie], flux: list[FluxTresorerie]
) -> PositionTresorerie:
    """Position par compte (réalisée et projetée) + consolidation par devise."""
    agg: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"enc": _ZERO, "dec": _ZERO, "enc_p": _ZERO, "dec_p": _ZERO}
    )
    for f in flux:
        a = agg[f.compte_code]
        if f.statut == "realise":
            a["enc" if f.sens == "encaissement" else "dec"] += f.montant_xaf
        else:  # prevu
            a["enc_p" if f.sens == "encaissement" else "dec_p"] += f.montant_xaf

    par_compte: list[CompteLigne] = []
    par_devise: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    total_realise = _ZERO
    total_projete = _ZERO
    for c in comptes:
        a = agg.get(c.code, {"enc": _ZERO, "dec": _ZERO, "enc_p": _ZERO, "dec_p": _ZERO})
        solde_realise = c.solde_initial_xaf + a["enc"] - a["dec"]
        solde_projete = solde_realise + a["enc_p"] - a["dec_p"]
        par_compte.append(
            CompteLigne(
                code=c.code,
                libelle=c.libelle,
                type=c.type,
                devise=c.devise,
                solde_initial_xaf=_xaf(c.solde_initial_xaf),
                encaisse_xaf=_xaf(a["enc"]),
                decaisse_xaf=_xaf(a["dec"]),
                solde_realise_xaf=_xaf(solde_realise),
                encaisse_prevu_xaf=_xaf(a["enc_p"]),
                decaisse_prevu_xaf=_xaf(a["dec_p"]),
                solde_projete_xaf=_xaf(solde_projete),
            )
        )
        par_devise[c.devise] += solde_realise
        total_realise += solde_realise
        total_projete += solde_projete

    return PositionTresorerie(
        nb_comptes=len(comptes),
        total_realise_xaf=_xaf(total_realise),
        total_projete_xaf=_xaf(total_projete),
        par_devise={d: str(_xaf(v)) for d, v in sorted(par_devise.items())},
        par_compte=par_compte,
    )


# ----------------------------------------------------------------- rapprochement bancaire


class LigneReleve(BaseModel):
    model_config = {"extra": "forbid"}

    date: date
    montant_xaf: Decimal
    sens: str  # encaissement | decaissement
    libelle: str = ""


class FluxRapprochable(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    compte_code: str = ""
    sens: str = "encaissement"
    montant_xaf: Decimal = Field(default=_ZERO)
    date_operation: date


@dataclass(frozen=True)
class Rapprochement:
    flux_id: str
    releve_index: int
    montant_xaf: Decimal


@dataclass(frozen=True)
class RapprochementResult:
    rapprochements: list[Rapprochement]
    flux_non_rapproches: list[str]
    releve_non_rapproche: list[int]
    taux_rapprochement_pct: Decimal


def rapprocher(
    flux: list[FluxRapprochable], releve: list[LigneReleve], *, fenetre_jours: int = 5
) -> RapprochementResult:
    """Apparie le relevé bancaire aux flux **réalisés** (montant + sens + fenêtre de date).

    Déterministe, appariement glouton 1↔1 ; la fenêtre tolère un décalage de date.
    """
    used_flux: set[str] = set()
    rapprochements: list[Rapprochement] = []
    releve_ok: set[int] = set()
    for i, ligne in enumerate(releve):
        for f in flux:
            if f.id in used_flux:
                continue
            if f.sens != ligne.sens or f.montant_xaf != ligne.montant_xaf:
                continue
            if abs((f.date_operation - ligne.date).days) > fenetre_jours:
                continue
            used_flux.add(f.id)
            releve_ok.add(i)
            rapprochements.append(
                Rapprochement(flux_id=f.id, releve_index=i, montant_xaf=_xaf(f.montant_xaf))
            )
            break
    flux_non = [f.id for f in flux if f.id not in used_flux]
    releve_non = [i for i in range(len(releve)) if i not in releve_ok]
    total = len(releve)
    taux = (
        (Decimal(len(releve_ok)) / Decimal(total) * 100).quantize(Decimal("0.1"))
        if total
        else _ZERO
    )
    return RapprochementResult(
        rapprochements=rapprochements,
        flux_non_rapproches=flux_non,
        releve_non_rapproche=releve_non,
        taux_rapprochement_pct=taux,
    )
