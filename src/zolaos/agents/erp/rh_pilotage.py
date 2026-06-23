"""SIRH — pilotage RH déterministe (indicateurs, échéancier, registre légal).

Doctrine : **déterministe d'abord** — tous les indicateurs RH sont calculés en
code (exacts, explicables) ; le LLM (agent RH) ne fait qu'interpréter/rédiger.
Entrées = modèles RH simples (alimentés depuis le store) ; sorties = dataclasses
sérialisables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")


# --------------------------------------------------------------------- entrées


class EmployeeHR(BaseModel):
    matricule: str
    nom_complet: str
    genre: str = "NC"  # H | F | NC
    date_naissance: date | None = None
    date_embauche: date
    poste: str = ""
    departement: str = ""
    manager_matricule: str | None = None
    categorie: str | None = None
    salaire_base_xaf: Decimal = Field(default=_ZERO, ge=0)
    quotite: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    statut: str = "actif"  # actif | sorti
    date_sortie: date | None = None


class ContractHR(BaseModel):
    employee_matricule: str
    type: str = "CDI"  # CDI | CDD | stage | prestation
    date_debut: date
    date_fin: date | None = None
    fin_periode_essai: date | None = None


class AbsenceHR(BaseModel):
    employee_matricule: str
    type: str = "conge_paye"
    date_debut: date
    date_fin: date
    jours: Decimal = Field(default=_ZERO, ge=0)


# --------------------------------------------------------------------- sorties


@dataclass(frozen=True)
class HrDashboard:
    effectif: int
    etp: str
    masse_salariale_xaf: str
    salaire_moyen_xaf: str
    anciennete_moyenne_annees: str
    turnover_pct: str
    absenteisme_pct: str
    ratio_encadrement_pct: str
    repartition_genre: dict[str, int]
    ecart_salarial_hf_pct: str
    par_departement: dict[str, int]
    par_type_contrat: dict[str, int]
    pyramide_ages: dict[str, int]


@dataclass(frozen=True)
class HrEcheance:
    categorie: str
    reference: str
    libelle: str
    date_cible: str
    jours_restants: int
    urgence: str


# --------------------------------------------------------------------- helpers


def _annees(d: date, today: date) -> Decimal:
    return Decimal((today - d).days) / Decimal("365.25")


def _tranche_age(naissance: date, today: date) -> str:
    ans = (today - naissance).days // 365
    if ans < 30:
        return "<30"
    if ans < 40:
        return "30-39"
    if ans < 50:
        return "40-49"
    return "50+"


def _urgence(jours: int) -> str:
    if jours < 15:
        return "high"
    if jours < 30:
        return "medium"
    return "low"


def _q2(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01")))


# --------------------------------------------------------------------- moteurs


def dashboard(
    employees: list[EmployeeHR],
    contracts: list[ContractHR],
    absences: list[AbsenceHR],
    *,
    today: date | None = None,
    periode_jours: int = 365,
) -> HrDashboard:
    """Indicateurs RH déterministes (sur les employés actifs)."""
    today = today or date.today()
    actifs = [e for e in employees if e.statut == "actif"]
    effectif = len(actifs)

    etp = sum((e.quotite for e in actifs), _ZERO)
    masse = sum((e.salaire_base_xaf for e in actifs), _ZERO)
    salaire_moyen = (masse / effectif) if effectif else _ZERO
    anciennete = (
        sum((_annees(e.date_embauche, today) for e in actifs), _ZERO) / effectif
        if effectif
        else _ZERO
    )

    # Turnover : sorties sur la période / effectif.
    sorties = [
        e
        for e in employees
        if e.date_sortie is not None and (today - e.date_sortie).days <= periode_jours
    ]
    turnover = (Decimal(len(sorties)) / effectif * 100) if effectif else _ZERO

    # Absentéisme : jours d'absence / jours ouvrés théoriques (220/an).
    jours_absence = sum((a.jours for a in absences), _ZERO)
    jours_ouvres = Decimal(effectif) * Decimal(periode_jours) * Decimal("220") / Decimal("365")
    absenteisme = (jours_absence / jours_ouvres * 100) if jours_ouvres > 0 else _ZERO

    encadrants = {e.manager_matricule for e in actifs if e.manager_matricule}
    ratio_encadrement = (Decimal(len(encadrants)) / effectif * 100) if effectif else _ZERO

    repartition_genre: dict[str, int] = {}
    par_departement: dict[str, int] = {}
    pyramide: dict[str, int] = {}
    for e in actifs:
        repartition_genre[e.genre] = repartition_genre.get(e.genre, 0) + 1
        dep = e.departement or "(non renseigné)"
        par_departement[dep] = par_departement.get(dep, 0) + 1
        if e.date_naissance is not None:
            t = _tranche_age(e.date_naissance, today)
            pyramide[t] = pyramide.get(t, 0) + 1

    salaires_h = [e.salaire_base_xaf for e in actifs if e.genre == "H"]
    salaires_f = [e.salaire_base_xaf for e in actifs if e.genre == "F"]
    moy_h = sum(salaires_h, _ZERO) / len(salaires_h) if salaires_h else _ZERO
    moy_f = sum(salaires_f, _ZERO) / len(salaires_f) if salaires_f else _ZERO
    ecart = ((moy_h - moy_f) / moy_h * 100) if moy_h > 0 else _ZERO

    par_type_contrat: dict[str, int] = {}
    actifs_matricules = {e.matricule for e in actifs}
    for c in contracts:
        if c.employee_matricule in actifs_matricules:
            par_type_contrat[c.type] = par_type_contrat.get(c.type, 0) + 1

    return HrDashboard(
        effectif=effectif,
        etp=_q2(etp),
        masse_salariale_xaf=str(masse),
        salaire_moyen_xaf=_q2(salaire_moyen),
        anciennete_moyenne_annees=_q2(anciennete),
        turnover_pct=_q2(turnover),
        absenteisme_pct=_q2(absenteisme),
        ratio_encadrement_pct=_q2(ratio_encadrement),
        repartition_genre=repartition_genre,
        ecart_salarial_hf_pct=_q2(ecart),
        par_departement=par_departement,
        par_type_contrat=par_type_contrat,
        pyramide_ages=pyramide,
    )


def echeancier(
    employees: list[EmployeeHR],
    contracts: list[ContractHR],
    *,
    today: date | None = None,
    horizon_jours: int = 60,
) -> list[HrEcheance]:
    """Échéances RH à venir : fin de période d'essai, fin de CDD, anniversaires."""
    today = today or date.today()
    nom = {e.matricule: e.nom_complet for e in employees}
    out: list[HrEcheance] = []

    for c in contracts:
        who = nom.get(c.employee_matricule, c.employee_matricule)
        if c.fin_periode_essai is not None:
            j = (c.fin_periode_essai - today).days
            if -horizon_jours <= j <= horizon_jours:
                out.append(
                    HrEcheance(
                        "periode_essai",
                        c.employee_matricule,
                        f"Fin de période d'essai — {who}",
                        c.fin_periode_essai.isoformat(),
                        j,
                        _urgence(j),
                    )
                )
        if c.type == "CDD" and c.date_fin is not None:
            j = (c.date_fin - today).days
            if -horizon_jours <= j <= horizon_jours:
                out.append(
                    HrEcheance(
                        "fin_cdd",
                        c.employee_matricule,
                        f"Fin de CDD — {who}",
                        c.date_fin.isoformat(),
                        j,
                        _urgence(j),
                    )
                )

    for e in employees:
        if e.statut != "actif":
            continue
        prochain = e.date_embauche.replace(year=today.year)
        if prochain < today:
            prochain = prochain.replace(year=today.year + 1)
        j = (prochain - today).days
        if 0 <= j <= horizon_jours:
            anciennete = prochain.year - e.date_embauche.year
            out.append(
                HrEcheance(
                    "anniversaire",
                    e.matricule,
                    f"{anciennete} an(s) d'ancienneté — {e.nom_complet}",
                    prochain.isoformat(),
                    j,
                    _urgence(j),
                )
            )

    return sorted(out, key=lambda x: x.jours_restants)


def registre(employees: list[EmployeeHR]) -> list[dict[str, str]]:
    """Registre unique du personnel (export légal), ordonné par date d'embauche."""
    ordered = sorted(employees, key=lambda e: e.date_embauche)
    return [
        {
            "matricule": e.matricule,
            "nom_complet": e.nom_complet,
            "genre": e.genre,
            "date_naissance": e.date_naissance.isoformat() if e.date_naissance else "",
            "date_embauche": e.date_embauche.isoformat(),
            "poste": e.poste,
            "departement": e.departement,
            "statut": e.statut,
            "date_sortie": e.date_sortie.isoformat() if e.date_sortie else "",
        }
        for e in ordered
    ]
