"""Trésorerie — moteur déterministe (position de caisse, consolidation).

**Aucun LLM** : la position de trésorerie est calculée en code (norme SYSCOHADA
classe 5). Position réalisée = solde initial + flux **réalisés** ; position
projetée = position réalisée + flux **prévus** (à venir).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from datetime import timedelta as _td
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


# ----------------------------------------------------------------- prévisionnel & pilotage


class FluxPrevu(BaseModel):
    model_config = {"extra": "forbid"}

    sens: str  # encaissement | decaissement
    montant_xaf: Decimal = Field(default=_ZERO)
    date: date


@dataclass(frozen=True)
class PeriodeForecast:
    libelle: str
    debut: str
    encaissements_xaf: Decimal
    decaissements_xaf: Decimal
    flux_net_xaf: Decimal
    solde_projete_xaf: Decimal


@dataclass(frozen=True)
class Previsionnel:
    position_initiale_xaf: Decimal
    encaissements_total_xaf: Decimal
    decaissements_total_xaf: Decimal
    position_finale_xaf: Decimal
    decouvert_periode: str | None
    decouvert_xaf: Decimal | None
    periodes: list[PeriodeForecast] = field(default_factory=list)


def previsionnel_tresorerie(
    position_initiale: Decimal,
    flux: list[FluxPrevu],
    *,
    as_of: date,
    horizon_jours: int = 90,
    pas_jours: int = 7,
) -> Previsionnel:
    """Projette le solde sur l'horizon (par pas), à partir des flux prévus.

    Déterministe : flux échus/à venir agrégés par période ; détecte le premier
    découvert (solde projeté négatif).
    """
    nb = max(1, -(-horizon_jours // pas_jours))  # arrondi supérieur
    buckets = [{"enc": _ZERO, "dec": _ZERO} for _ in range(nb)]
    for f in flux:
        delta = (f.date - as_of).days
        idx = 0 if delta < 0 else delta // pas_jours  # échus → 1re période
        if idx >= nb:
            continue
        buckets[idx]["enc" if f.sens == "encaissement" else "dec"] += f.montant_xaf

    cumul = position_initiale
    periodes: list[PeriodeForecast] = []
    enc_total = _ZERO
    dec_total = _ZERO
    decouvert_periode: str | None = None
    decouvert_xaf: Decimal | None = None
    for i, b in enumerate(buckets):
        net = b["enc"] - b["dec"]
        cumul += net
        enc_total += b["enc"]
        dec_total += b["dec"]
        debut = as_of + _td(i * pas_jours)
        lib = f"S{i + 1}"
        periodes.append(
            PeriodeForecast(
                libelle=lib,
                debut=debut.isoformat(),
                encaissements_xaf=_xaf(b["enc"]),
                decaissements_xaf=_xaf(b["dec"]),
                flux_net_xaf=_xaf(net),
                solde_projete_xaf=_xaf(cumul),
            )
        )
        if cumul < 0 and decouvert_periode is None:
            decouvert_periode = lib
            decouvert_xaf = _xaf(cumul)

    return Previsionnel(
        position_initiale_xaf=_xaf(position_initiale),
        encaissements_total_xaf=_xaf(enc_total),
        decaissements_total_xaf=_xaf(dec_total),
        position_finale_xaf=_xaf(cumul),
        decouvert_periode=decouvert_periode,
        decouvert_xaf=decouvert_xaf,
        periodes=periodes,
    )


@dataclass(frozen=True)
class IndicateursTreso:
    encours_clients_xaf: Decimal
    encours_fournisseurs_xaf: Decimal
    dso_jours: int
    dpo_jours: int
    bfr_xaf: Decimal
    runway_mois: Decimal | None


def indicateurs_tresorerie(
    *,
    encours_clients: Decimal,
    encours_fournisseurs: Decimal,
    ca: Decimal,
    achats: Decimal,
    valeur_stock: Decimal,
    position_actuelle: Decimal,
    net_mensuel_prevu: Decimal,
) -> IndicateursTreso:
    """DSO/DPO (jours), BFR et runway — déterministe, annualisé sur 365 j."""
    dso = int((encours_clients / ca * 365).quantize(Decimal("1"))) if ca > 0 else 0
    dpo = int((encours_fournisseurs / achats * 365).quantize(Decimal("1"))) if achats > 0 else 0
    bfr = encours_clients + valeur_stock - encours_fournisseurs
    runway = (
        (position_actuelle / -net_mensuel_prevu).quantize(Decimal("0.1"))
        if net_mensuel_prevu < 0 and position_actuelle > 0
        else None
    )
    return IndicateursTreso(
        encours_clients_xaf=_xaf(encours_clients),
        encours_fournisseurs_xaf=_xaf(encours_fournisseurs),
        dso_jours=dso,
        dpo_jours=dpo,
        bfr_xaf=_xaf(bfr),
        runway_mois=runway,
    )
