"""DAS 1 — agrégation annuelle de la paie (Déclaration Annuelle des Salaires, Congo).

**Aucun LLM** : consolidation déterministe des bulletins mensuels persistés en
deux états légaux — l'**état annuel brut & IRPP** (matrice salarié × 12 mois) et
la **DAS 1 / CNSS 1** (par salarié : brut, salaire plafonné CNSS, base imposable
= 80 % du brut, IRPP). Les identités proviennent du registre du personnel.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")
_MOIS = (
    "JANVIER",
    "FEVRIER",
    "MARS",
    "AVRIL",
    "MAI",
    "JUIN",
    "JUILLET",
    "AOUT",
    "SEPTEMBRE",
    "OCTOBRE",
    "NOVEMBRE",
    "DECEMBRE",
)


class LignePaie(BaseModel):
    """Un bulletin mensuel agrégeable (extrait de `store_payslips`)."""

    model_config = {"extra": "forbid"}

    matricule: str
    mois: int = Field(..., ge=1, le=12)
    brut_xaf: Decimal = _ZERO
    base_imposable_xaf: Decimal = _ZERO
    irpp_xaf: Decimal = _ZERO


class Salarie(BaseModel):
    """Identité d'un salarié (extrait de `store_employees`)."""

    model_config = {"extra": "forbid"}

    matricule: str
    nom: str = ""
    sexe: str = ""
    date_embauche: date | None = None
    date_depart: date | None = None
    profession: str = ""


def _xaf(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EtatAnnuelLigne:
    matricule: str
    nom: str
    mensuels_xaf: list[Decimal]  # 12 valeurs
    total_xaf: Decimal
    irpp_annuel_xaf: Decimal


@dataclass(frozen=True)
class Das1Ligne:
    matricule: str
    nom: str
    sexe: str
    date_embauche: str | None
    date_depart: str | None
    profession: str
    brut_annuel_xaf: Decimal
    salaire_plafonne_xaf: Decimal
    base_imposable_xaf: Decimal
    irpp_xaf: Decimal


@dataclass(frozen=True)
class Das1:
    exercice: str
    nb_salaries: int
    total_brut_xaf: Decimal
    total_plafonne_xaf: Decimal
    total_base_imposable_xaf: Decimal
    total_irpp_xaf: Decimal
    etat_annuel: list[EtatAnnuelLigne] = field(default_factory=list)
    lignes: list[Das1Ligne] = field(default_factory=list)


def construire_das1(
    lignes_paie: list[LignePaie],
    salaries: list[Salarie],
    *,
    exercice: str,
    plafond_mensuel_xaf: Decimal | None = None,
) -> Das1:
    """Consolide les bulletins mensuels en état annuel + DAS 1 (déterministe).

    `plafond_mensuel_xaf` (barème CNSS) borne le salaire plafonné mensuel ;
    None ⇒ pas de plafonnement.
    """
    noms = {s.matricule: s.nom for s in salaries}
    par_sal = {s.matricule: s for s in salaries}

    # agrégats par matricule
    mensuels: dict[str, list[Decimal]] = defaultdict(lambda: [_ZERO] * 12)
    plafonne: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    base_imp: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    irpp: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for lp in lignes_paie:
        mensuels[lp.matricule][lp.mois - 1] += lp.brut_xaf
        base_imp[lp.matricule] += lp.base_imposable_xaf
        irpp[lp.matricule] += lp.irpp_xaf
        plaf = (
            min(lp.brut_xaf, plafond_mensuel_xaf)
            if plafond_mensuel_xaf is not None
            else lp.brut_xaf
        )
        plafonne[lp.matricule] += plaf

    matricules = sorted(set(mensuels) | {s.matricule for s in salaries})

    etat: list[EtatAnnuelLigne] = []
    das1_lignes: list[Das1Ligne] = []
    t_brut = t_plaf = t_base = t_irpp = _ZERO
    for m in matricules:
        cols = [_xaf(v) for v in mensuels.get(m, [_ZERO] * 12)]
        total = sum(cols, _ZERO)
        irpp_m = _xaf(irpp.get(m, _ZERO))
        etat.append(
            EtatAnnuelLigne(
                matricule=m,
                nom=noms.get(m, ""),
                mensuels_xaf=cols,
                total_xaf=total,
                irpp_annuel_xaf=irpp_m,
            )
        )
        s = par_sal.get(m)
        brut_a = total
        plaf_a = _xaf(plafonne.get(m, _ZERO))
        base_a = _xaf(base_imp.get(m, _ZERO))
        das1_lignes.append(
            Das1Ligne(
                matricule=m,
                nom=noms.get(m, ""),
                sexe=s.sexe if s else "",
                date_embauche=s.date_embauche.isoformat() if s and s.date_embauche else None,
                date_depart=s.date_depart.isoformat() if s and s.date_depart else None,
                profession=s.profession if s else "",
                brut_annuel_xaf=brut_a,
                salaire_plafonne_xaf=plaf_a,
                base_imposable_xaf=base_a,
                irpp_xaf=irpp_m,
            )
        )
        t_brut += brut_a
        t_plaf += plaf_a
        t_base += base_a
        t_irpp += irpp_m

    return Das1(
        exercice=exercice,
        nb_salaries=len(matricules),
        total_brut_xaf=t_brut,
        total_plafonne_xaf=t_plaf,
        total_base_imposable_xaf=t_base,
        total_irpp_xaf=t_irpp,
        etat_annuel=etat,
        lignes=das1_lignes,
    )


def libelle_mois(i: int) -> str:
    """Libellé du mois (1-12)."""
    return _MOIS[i - 1]
