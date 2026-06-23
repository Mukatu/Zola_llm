"""SIRH — pilotage du recrutement (déterministe).

Indicateurs calculés en code sur les registres (vacances, candidats,
candidatures) : entonnoir, time-to-hire, efficacité des sources, aging des
vacances. Le LLM (SIRH-2b) génère séparément fiches/grilles/contrats.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

# Étapes canoniques du pipeline (ordre).
ETAPES: tuple[str, ...] = ("reçue", "présélection", "entretien", "offre", "embauché")
_TERMINALES = {"rejeté", "désisté"}
_VACANCE_OUVERTE = {"ouverte", "en cours", "gelée"}


class VacancyRef(BaseModel):
    code_vacance: str
    code_emploi: str | None = None
    statut: str = "ouverte"
    date_ouverture: date
    date_cible: date | None = None
    budget_xaf: Decimal | None = None


class CandidateRef(BaseModel):
    id: str
    source: str = "inconnue"


class ApplicationRef(BaseModel):
    candidate_id: str
    code_vacance: str
    etape: str = "reçue"
    date_candidature: date
    date_etape: date | None = None


def _q1(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.1")))


def recruitment_dashboard(
    vacancies: list[VacancyRef],
    candidates: list[CandidateRef],
    applications: list[ApplicationRef],
    *,
    today: date | None = None,
    seuil_aging_jours: int = 30,
) -> dict[str, object]:
    """Indicateurs de recrutement déterministes."""
    today = today or date.today()
    total = len(applications)

    par_etape = {e: 0 for e in ETAPES}
    for a in applications:
        if a.etape in par_etape:
            par_etape[a.etape] += 1
    rejetes = sum(1 for a in applications if a.etape in _TERMINALES)
    embauches = par_etape["embauché"]
    taux_embauche = (Decimal(embauches) / Decimal(total) * 100) if total else Decimal("0")

    # Time-to-hire : date d'embauche − date d'ouverture de la vacance.
    ouverture = {v.code_vacance: v.date_ouverture for v in vacancies}
    delais = [
        (a.date_etape - ouverture[a.code_vacance]).days
        for a in applications
        if a.etape == "embauché" and a.date_etape is not None and a.code_vacance in ouverture
    ]
    tth = (Decimal(sum(delais)) / Decimal(len(delais))) if delais else Decimal("0")

    # Efficacité des sources.
    src_by_cand = {c.id: c.source for c in candidates}
    par_source: dict[str, dict[str, int]] = {}
    for a in applications:
        src = src_by_cand.get(a.candidate_id, "inconnue")
        bucket = par_source.setdefault(src, {"candidatures": 0, "embauches": 0})
        bucket["candidatures"] += 1
        if a.etape == "embauché":
            bucket["embauches"] += 1

    # Aging des vacances ouvertes (jours typé int → tri propre).
    aging_pairs: list[tuple[int, dict[str, object]]] = []
    for v in vacancies:
        if v.statut not in _VACANCE_OUVERTE:
            continue
        jours = (today - v.date_ouverture).days
        if jours > seuil_aging_jours:
            aging_pairs.append(
                (
                    jours,
                    {"code_vacance": v.code_vacance, "jours_ouverte": jours, "statut": v.statut},
                )
            )
    aging = [d for _, d in sorted(aging_pairs, key=lambda p: -p[0])]

    return {
        "total_candidatures": total,
        "par_etape": par_etape,
        "rejetes": rejetes,
        "embauches": embauches,
        "taux_embauche_pct": _q1(taux_embauche),
        "time_to_hire_jours": _q1(tth),
        "par_source": par_source,
        "vacances_en_souffrance": aging,
    }
