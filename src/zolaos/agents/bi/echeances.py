"""Échéances réglementaires — **rappels indicatifs** paramétrables.

Ce module ne fait pas autorité : il fournit une cadence de rappels (mensuel /
trimestriel / annuel) pour ne pas oublier une obligation. Chaque échéance est
marquée ``indicatif`` et invite à confirmer la date exacte auprès de
l'administration ou du conseil. Les valeurs sont éditables sans toucher au code
appelant — même esprit que le barème de paie (paramétrable, gouverné).
"""

from __future__ import annotations

import calendar
from datetime import date

from pydantic import BaseModel

_NOTE = "Rappel indicatif — confirmez la date exacte auprès de l'administration ou de votre conseil."

# Obligations courantes (cadence indicative). periodicite : mensuelle | trimestrielle | annuelle.
# jour = jour limite dans le mois ; mois (annuelle) = mois de l'échéance.
OBLIGATIONS: list[dict[str, object]] = [
    {"code": "tva", "libelle": "TVA — déclaration & paiement", "periodicite": "mensuelle", "jour": 20},
    {"code": "cnss", "libelle": "CNSS — cotisations sociales", "periodicite": "mensuelle", "jour": 15},
    {"code": "its", "libelle": "IRPP/ITS — retenues sur salaires", "periodicite": "mensuelle", "jour": 15},
    {"code": "is_acompte", "libelle": "IS — acompte", "periodicite": "trimestrielle", "jour": 20},
    {"code": "das1", "libelle": "DAS1 — déclaration annuelle des salaires", "periodicite": "annuelle", "jour": 31, "mois": 3},
]


class Echeance(BaseModel):
    code: str
    libelle: str
    periodicite: str
    date_limite: date
    jours_restants: int
    indicatif: bool = True
    note: str = _NOTE


def _clamp_jour(annee: int, mois: int, jour: int) -> date:
    """Ramène le jour au dernier jour du mois si nécessaire (ex. 31 → 30)."""
    dernier = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, min(jour, dernier))


def _prochaine_mensuelle(today: date, jour: int) -> date:
    cible = _clamp_jour(today.year, today.month, jour)
    if cible >= today:
        return cible
    mois = today.month + 1
    annee = today.year + (mois - 1) // 12
    mois = (mois - 1) % 12 + 1
    return _clamp_jour(annee, mois, jour)


def _prochaine_trimestrielle(today: date, jour: int) -> date:
    for mois in (1, 4, 7, 10):
        cible = _clamp_jour(today.year, mois, jour)
        if cible >= today:
            return cible
    return _clamp_jour(today.year + 1, 1, jour)


def _prochaine_annuelle(today: date, mois: int, jour: int) -> date:
    cible = _clamp_jour(today.year, mois, jour)
    if cible >= today:
        return cible
    return _clamp_jour(today.year + 1, mois, jour)


def prochaines_echeances(today: date | None = None, *, horizon_jours: int = 120) -> list[Echeance]:
    """Prochaines échéances dans l'horizon (par défaut 120 j), triées par date."""
    jour_ref = today or date.today()
    out: list[Echeance] = []
    for o in OBLIGATIONS:
        periodicite = str(o["periodicite"])
        jour = int(o["jour"])  # type: ignore[call-overload]
        if periodicite == "mensuelle":
            d = _prochaine_mensuelle(jour_ref, jour)
        elif periodicite == "trimestrielle":
            d = _prochaine_trimestrielle(jour_ref, jour)
        else:
            d = _prochaine_annuelle(jour_ref, int(o.get("mois", 1)), jour)  # type: ignore[arg-type]
        restants = (d - jour_ref).days
        if restants <= horizon_jours:
            out.append(
                Echeance(
                    code=str(o["code"]),
                    libelle=str(o["libelle"]),
                    periodicite=periodicite,
                    date_limite=d,
                    jours_restants=restants,
                )
            )
    out.sort(key=lambda e: e.date_limite)
    return out
