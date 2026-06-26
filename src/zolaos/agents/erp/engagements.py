"""Engagements d'achats — moteur déterministe (chaîne EB → DA → BC).

Pilotage des engagements : suivi du workflow Expression de Besoin → Demande
d'Achat → Bon de Commande, transformation, écart estimation/engagé, répartition
par direction et acheteur, funnel des statuts, délais de cycle et alertes.

**Aucun LLM** : tout est calculé en code (inspiré de l'outil métier réel des achats).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")


class Engagement(BaseModel):
    model_config = {"extra": "forbid"}

    numero_eb: str
    numero_da: str | None = None
    numero_bc: str | None = None
    date_eb: date | None = None
    date_da: date | None = None
    date_bc: date | None = None
    direction: str | None = None
    service: str | None = None
    demandeur: str | None = None
    acheteur: str | None = None
    fournisseur: str | None = None
    estimation_xaf: Decimal = Field(default=_ZERO)
    montant_xaf: Decimal = Field(default=_ZERO)
    statut_ebda: str = ""
    statut_bc: str = ""


def _pct(part: int, whole: int) -> Decimal:
    if whole <= 0:
        return _ZERO
    return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _is_annule(e: Engagement) -> bool:
    return "annul" in e.statut_ebda.lower() or "annul" in e.statut_bc.lower()


def _is_traite(e: Engagement) -> bool:
    return e.statut_bc.strip().lower().startswith("trait")


def phase(e: Engagement) -> str:
    """Étape atteinte : annulee | traite | commande | demande | besoin (déterministe)."""
    if _is_annule(e):
        return "annulee"
    if _is_traite(e):
        return "traite"
    if e.numero_bc:
        return "commande"
    if e.numero_da:
        return "demande"
    return "besoin"


# ----------------------------------------------------------------- statistiques


@dataclass(frozen=True)
class DimensionLigne:
    cle: str
    nb: int
    engage_xaf: Decimal
    estimation_xaf: Decimal


@dataclass(frozen=True)
class EngagementStats:
    nb_total: int
    par_phase: dict[str, int]
    nb_eb: int
    nb_da: int
    nb_bc: int
    taux_eb_vers_da_pct: Decimal
    taux_da_vers_bc_pct: Decimal
    taux_eb_vers_bc_pct: Decimal
    estimation_totale_xaf: Decimal
    engage_total_xaf: Decimal
    ecart_xaf: Decimal  # engagé - estimation (positif = dépassement global)
    nb_depassements: int
    par_direction: list[DimensionLigne]
    par_acheteur: list[DimensionLigne]
    funnel_statut_bc: dict[str, int]
    delai_moyen_eb_da_jours: int | None
    delai_moyen_da_bc_jours: int | None


def _dimension(engagements: list[Engagement], key: str) -> list[DimensionLigne]:
    agg: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"nb": _ZERO, "engage": _ZERO, "estim": _ZERO}
    )
    for e in engagements:
        cle = (getattr(e, key) or "—").strip() or "—"
        agg[cle]["nb"] += 1
        agg[cle]["engage"] += e.montant_xaf
        agg[cle]["estim"] += e.estimation_xaf
    lignes = [
        DimensionLigne(
            cle=cle,
            nb=int(v["nb"]),
            engage_xaf=_xaf(v["engage"]),
            estimation_xaf=_xaf(v["estim"]),
        )
        for cle, v in agg.items()
    ]
    return sorted(lignes, key=lambda x: x.engage_xaf, reverse=True)


def _delai_moyen(engagements: list[Engagement], d1: str, d2: str) -> int | None:
    jours = [
        (getattr(e, d2) - getattr(e, d1)).days
        for e in engagements
        if getattr(e, d1) is not None and getattr(e, d2) is not None
    ]
    jours = [j for j in jours if j >= 0]
    if not jours:
        return None
    return round(sum(jours) / len(jours))


def engagement_stats(engagements: list[Engagement]) -> EngagementStats:
    actifs = [e for e in engagements if not _is_annule(e)]
    par_phase: dict[str, int] = defaultdict(int)
    for e in engagements:
        par_phase[phase(e)] += 1

    nb_eb = sum(1 for e in actifs if e.numero_eb)
    nb_da = sum(1 for e in actifs if e.numero_da)
    nb_bc = sum(1 for e in actifs if e.numero_bc)

    estimation = sum((e.estimation_xaf for e in actifs), _ZERO)
    engage = sum((e.montant_xaf for e in actifs), _ZERO)
    nb_depassements = sum(
        1 for e in actifs if e.estimation_xaf > 0 and e.montant_xaf > e.estimation_xaf
    )

    funnel: dict[str, int] = defaultdict(int)
    for e in actifs:
        if e.numero_bc:
            funnel[e.statut_bc.strip() or "—"] += 1

    return EngagementStats(
        nb_total=len(engagements),
        par_phase=dict(par_phase),
        nb_eb=nb_eb,
        nb_da=nb_da,
        nb_bc=nb_bc,
        taux_eb_vers_da_pct=_pct(nb_da, nb_eb),
        taux_da_vers_bc_pct=_pct(nb_bc, nb_da),
        taux_eb_vers_bc_pct=_pct(nb_bc, nb_eb),
        estimation_totale_xaf=_xaf(estimation),
        engage_total_xaf=_xaf(engage),
        ecart_xaf=_xaf(engage - estimation),
        nb_depassements=nb_depassements,
        par_direction=_dimension(actifs, "direction"),
        par_acheteur=_dimension(actifs, "acheteur"),
        funnel_statut_bc=dict(funnel),
        delai_moyen_eb_da_jours=_delai_moyen(actifs, "date_eb", "date_da"),
        delai_moyen_da_bc_jours=_delai_moyen(actifs, "date_da", "date_bc"),
    )


# ----------------------------------------------------------------- alertes


@dataclass(frozen=True)
class EngagementAlerte:
    type: str  # depassement | bloque
    reference: str
    libelle: str
    priorite: str  # high | medium


def detect_alertes(
    engagements: list[Engagement], *, as_of: date | None = None, seuil_jours: int = 30
) -> list[EngagementAlerte]:
    """Dépassements d'estimation et engagements bloqués (anciens, non traités/non commandés)."""
    as_of = as_of or date.today()
    out: list[EngagementAlerte] = []
    for e in engagements:
        if _is_annule(e):
            continue
        if e.estimation_xaf > 0 and e.montant_xaf > e.estimation_xaf:
            ecart = e.montant_xaf - e.estimation_xaf
            out.append(
                EngagementAlerte(
                    "depassement",
                    e.numero_eb,
                    f"{e.numero_eb} : engagé {_xaf(e.montant_xaf)} > estimation "
                    f"{_xaf(e.estimation_xaf)} (+{_xaf(ecart)} XAF)",
                    "high",
                )
            )
        ref_date = e.date_da or e.date_eb
        if (
            not _is_traite(e)
            and not e.numero_bc
            and ref_date is not None
            and (as_of - ref_date).days >= seuil_jours
        ):
            jours = (as_of - ref_date).days
            out.append(
                EngagementAlerte(
                    "bloque",
                    e.numero_eb,
                    f"{e.numero_eb} sans BC depuis {jours} j (statut : {e.statut_ebda or '—'})",
                    "medium",
                )
            )
    return out
