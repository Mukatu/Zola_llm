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
    """Un bulletin mensuel agrégeable (extrait de `store_payslips`).

    `cotisations_salariales_xaf` = cotisations salariales retenues (retraite CNSS),
    déjà plafonnées au mois par le calculateur de paie ; la DAS 1 les déduit du
    brut pour obtenir le **salaire plafonné** (brut net de retraite).
    """

    model_config = {"extra": "forbid"}

    matricule: str
    mois: int = Field(..., ge=1, le=12)
    brut_xaf: Decimal = _ZERO
    cotisations_salariales_xaf: Decimal = _ZERO
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
    livret_cnss: str = ""
    n_contribuable: str = ""
    situation_matrimoniale: str = ""
    nationalite: str = ""
    nb_enfants: int = 0


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
    livret_cnss: str
    n_contribuable: str
    situation_matrimoniale: str
    nationalite: str
    nb_enfants: int
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
    abattement_taux: Decimal = Decimal("0.20"),
) -> Das1:
    """Consolide les bulletins mensuels en état annuel + DAS 1 (déterministe).

    Règles légales reproduites du formulaire DAS 1 / CNSS 1 (Congo) :
    - **salaire plafonné** = brut annuel − cotisations salariales (retraite CNSS,
      déjà plafonnées au mois) ;
    - **base imposable** = (1 − `abattement_taux`) × salaire plafonné
      (abattement de 20 % ⇒ 80 % du salaire net de retraite).
    """
    noms = {s.matricule: s.nom for s in salaries}
    par_sal = {s.matricule: s for s in salaries}
    abattement = Decimal("1") - abattement_taux

    # agrégats par matricule
    mensuels: dict[str, list[Decimal]] = defaultdict(lambda: [_ZERO] * 12)
    cotis: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    irpp: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for lp in lignes_paie:
        mensuels[lp.matricule][lp.mois - 1] += lp.brut_xaf
        cotis[lp.matricule] += lp.cotisations_salariales_xaf
        irpp[lp.matricule] += lp.irpp_xaf

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
        plaf_a = brut_a - _xaf(cotis.get(m, _ZERO))  # salaire net de retraite
        base_a = _xaf(abattement * plaf_a)  # 80 % du salaire plafonné
        das1_lignes.append(
            Das1Ligne(
                matricule=m,
                nom=noms.get(m, ""),
                sexe=s.sexe if s else "",
                date_embauche=s.date_embauche.isoformat() if s and s.date_embauche else None,
                date_depart=s.date_depart.isoformat() if s and s.date_depart else None,
                profession=s.profession if s else "",
                livret_cnss=s.livret_cnss if s else "",
                n_contribuable=s.n_contribuable if s else "",
                situation_matrimoniale=s.situation_matrimoniale if s else "",
                nationalite=s.nationalite if s else "",
                nb_enfants=s.nb_enfants if s else 0,
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
