"""SIRH — évaluations & revue de talents (déterministe).

Matrice 9-box (performance × potentiel), distribution, top talents et
sous-performeurs. Calculs en code ; le LLM (séparément) rédige PDI et supports
d'entretien.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_NIVEAUX = ("bas", "moyen", "haut")


class EvaluationRef(BaseModel):
    matricule: str
    nom_complet: str = ""
    periode: str = ""
    performance: int = Field(default=3, ge=1, le=5)
    potentiel: int = Field(default=3, ge=1, le=5)


def _niveau(n: int) -> str:
    if n <= 2:
        return "bas"
    if n == 3:
        return "moyen"
    return "haut"


def talent_review(evaluations: list[EvaluationRef]) -> dict[str, object]:
    """Revue de talents : matrice 9-box + listes clés (déterministe)."""
    grid: dict[str, list[str]] = {f"{p}/{pot}": [] for p in _NIVEAUX for pot in _NIVEAUX}
    distribution_perf = {n: 0 for n in _NIVEAUX}
    top_talents: list[str] = []
    sous_performeurs: list[str] = []

    for ev in evaluations:
        perf, pot = _niveau(ev.performance), _niveau(ev.potentiel)
        grid[f"{perf}/{pot}"].append(ev.matricule)
        distribution_perf[perf] += 1
        if perf == "haut" and pot == "haut":
            top_talents.append(ev.matricule)
        if perf == "bas":
            sous_performeurs.append(ev.matricule)

    return {
        "grid": grid,
        "distribution_performance": distribution_perf,
        "top_talents": top_talents,
        "sous_performeurs": sous_performeurs,
        "hauts_potentiels": [ev.matricule for ev in evaluations if ev.potentiel >= 4],
    }
