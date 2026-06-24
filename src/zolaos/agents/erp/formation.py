"""SIRH — pilotage de la formation (déterministe).

Indicateurs calculés en code sur les registres (catalogue, sessions,
inscriptions, évaluations à chaud/à froid) : taux de réalisation, coûts,
heures/employé, satisfaction, efficacité, échéancier. Le LLM (séparément)
génère le plan de formation et les formulaires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")


class TrainingRef(BaseModel):
    code: str
    intitule: str = ""
    competences_visees: list[str] = Field(default_factory=list)
    duree_heures: Decimal = Field(default=_ZERO, ge=0)
    cout_xaf: Decimal = Field(default=_ZERO, ge=0)


class SessionRef(BaseModel):
    id: str
    training_code: str
    date_debut: date
    date_fin: date | None = None
    statut: str = "planifiee"


class EnrollmentRef(BaseModel):
    id: str
    session_id: str
    employee_matricule: str
    statut: str = "inscrit"  # inscrit | realise | annule | absent


class TrainingEvalRef(BaseModel):
    enrollment_id: str
    type: str = "chaud"  # chaud | froid
    satisfaction: int | None = None  # /5 (à chaud)
    acquis: int | None = None  # /5 (à froid)


@dataclass(frozen=True)
class FormationDashboard:
    nb_formations: int
    nb_sessions: int
    nb_inscriptions: int
    nb_realisees: int
    taux_realisation_pct: str
    cout_total_xaf: str
    cout_par_employe_xaf: str
    heures_par_employe: str
    satisfaction_moyenne: str
    efficacite_moyenne: str
    competences_visees: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FormationEcheance:
    categorie: str
    reference: str
    libelle: str
    date_cible: str
    jours_restants: int
    urgence: str


def _q1(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.1")))


def _urgence(j: int) -> str:
    if j < 7:
        return "high"
    if j < 21:
        return "medium"
    return "low"


def formation_dashboard(
    trainings: list[TrainingRef],
    sessions: list[SessionRef],
    enrollments: list[EnrollmentRef],
    evaluations: list[TrainingEvalRef],
) -> FormationDashboard:
    by_code = {t.code: t for t in trainings}
    sess_training = {s.id: s.training_code for s in sessions}

    inscrits = [e for e in enrollments if e.statut in {"inscrit", "realise", "absent"}]
    realises = [e for e in enrollments if e.statut == "realise"]
    taux = (Decimal(len(realises)) / Decimal(len(inscrits)) * 100) if inscrits else _ZERO

    cout_total = _ZERO
    heures_total = _ZERO
    for e in realises:
        t = by_code.get(sess_training.get(e.session_id, ""))
        if t is not None:
            cout_total += t.cout_xaf
            heures_total += t.duree_heures
    employes = {e.employee_matricule for e in realises}
    nb_emp = len(employes)
    cout_emp = (cout_total / nb_emp) if nb_emp else _ZERO
    heures_emp = (heures_total / nb_emp) if nb_emp else _ZERO

    chaud = [
        ev.satisfaction for ev in evaluations if ev.type == "chaud" and ev.satisfaction is not None
    ]
    froid = [ev.acquis for ev in evaluations if ev.type == "froid" and ev.acquis is not None]
    satis = (Decimal(sum(chaud)) / Decimal(len(chaud))) if chaud else _ZERO
    effic = (Decimal(sum(froid)) / Decimal(len(froid))) if froid else _ZERO

    visees = sorted({c for t in trainings for c in t.competences_visees})

    return FormationDashboard(
        nb_formations=len(trainings),
        nb_sessions=len(sessions),
        nb_inscriptions=len(inscrits),
        nb_realisees=len(realises),
        taux_realisation_pct=_q1(taux),
        cout_total_xaf=str(cout_total),
        cout_par_employe_xaf=_q1(cout_emp),
        heures_par_employe=_q1(heures_emp),
        satisfaction_moyenne=_q1(satis),
        efficacite_moyenne=_q1(effic),
        competences_visees=visees,
    )


def formation_echeancier(
    sessions: list[SessionRef],
    enrollments: list[EnrollmentRef],
    evaluations: list[TrainingEvalRef],
    *,
    today: date | None = None,
    horizon_jours: int = 60,
) -> list[FormationEcheance]:
    today = today or date.today()
    out: list[FormationEcheance] = []

    for s in sessions:
        if s.statut in {"annulee", "realisee"}:
            continue
        j = (s.date_debut - today).days
        if 0 <= j <= horizon_jours:
            out.append(
                FormationEcheance(
                    "session",
                    s.id,
                    f"Session {s.training_code}",
                    s.date_debut.isoformat(),
                    j,
                    _urgence(j),
                )
            )

    # Évaluations à froid manquantes pour les inscriptions réalisées.
    froid_done = {ev.enrollment_id for ev in evaluations if ev.type == "froid"}
    for e in enrollments:
        if e.statut == "realise" and e.id not in froid_done:
            out.append(
                FormationEcheance(
                    "eval_froid",
                    e.id,
                    f"Évaluation à froid à planifier — {e.employee_matricule}",
                    "",
                    0,
                    "medium",
                )
            )

    return sorted(out, key=lambda x: x.jours_restants)
