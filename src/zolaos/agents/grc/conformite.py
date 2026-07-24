"""Plan de contrôle & synthèse de conformité — déterministe (GRC-1).

À partir du registre persisté (obligations, contrôles, constats), le moteur
calcule une synthèse de pilotage de la conformité : couverture des obligations
par des contrôles, contrôles en retard, échéances à venir, taux de conformité
(constats résolus). Aucune valeur normative n'est inventée — le moteur agrège
ce que le cabinet a saisi ; le LLM ne fait que narrer.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

_GRAVITES = ("critique", "majeur", "mineur")


class ObligationLite(BaseModel):
    id: str
    reference: str = ""
    intitule: str = ""
    domaine: str = "autre"
    echeance: date | None = None
    statut: str = "active"


class ControlLite(BaseModel):
    id: str
    obligation_id: str | None = None
    intitule: str = ""
    prochaine_execution: date | None = None
    statut: str = "planifie"


class FindingLite(BaseModel):
    id: str
    gravite: str = "mineur"
    statut: str = "ouvert"
    echeance_correction: date | None = None


class EcheanceGrc(BaseModel):
    type: str  # obligation | controle
    reference: str
    libelle: str
    date_limite: date
    jours_restants: int


class SyntheseConformite(BaseModel):
    nb_obligations: int
    nb_obligations_actives: int
    nb_obligations_sans_controle: int
    taux_couverture: Decimal  # % obligations actives couvertes par ≥1 contrôle
    nb_controls: int
    nb_controls_en_retard: int
    nb_findings: int
    nb_findings_ouverts: int
    taux_conformite: Decimal  # % constats résolus
    findings_ouverts_par_gravite: dict[str, int]
    obligations_par_domaine: dict[str, int]
    echeances: list[EcheanceGrc]
    alertes: list[str]


def _pct(n: int, d: int) -> Decimal:
    if d <= 0:
        return Decimal("0")
    return (Decimal(n) / Decimal(d) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def synthese_conformite(
    obligations: Iterable[ObligationLite],
    controls: Iterable[ControlLite],
    findings: Iterable[FindingLite],
    *,
    today: date,
    horizon_jours: int = 90,
) -> SyntheseConformite:
    """Agrège le registre de conformité en une synthèse de pilotage (déterministe)."""
    obs = list(obligations)
    ctrls = list(controls)
    finds = list(findings)

    actives = [o for o in obs if o.statut == "active"]
    couvertes = {c.obligation_id for c in ctrls if c.obligation_id}
    sans_controle = [o for o in actives if o.id not in couvertes]

    # Contrôles en retard : prochaine exécution dépassée et non réalisés.
    en_retard = [
        c
        for c in ctrls
        if c.prochaine_execution is not None
        and c.prochaine_execution < today
        and c.statut != "realise"
    ]

    ouverts = [f for f in finds if f.statut != "resolu"]
    resolus = [f for f in finds if f.statut == "resolu"]
    par_gravite = {g: sum(1 for f in ouverts if f.gravite == g) for g in _GRAVITES}

    par_domaine: dict[str, int] = {}
    for o in obs:
        par_domaine[o.domaine] = par_domaine.get(o.domaine, 0) + 1

    # Échéances à venir (obligations + prochaines exécutions de contrôles).
    echeances: list[EcheanceGrc] = []
    for o in actives:
        if o.echeance is not None:
            j = (o.echeance - today).days
            if j <= horizon_jours:
                echeances.append(
                    EcheanceGrc(
                        type="obligation",
                        reference=o.reference or o.id[:8],
                        libelle=o.intitule,
                        date_limite=o.echeance,
                        jours_restants=j,
                    )
                )
    for c in ctrls:
        if c.prochaine_execution is not None and c.statut != "realise":
            j = (c.prochaine_execution - today).days
            if j <= horizon_jours:
                echeances.append(
                    EcheanceGrc(
                        type="controle",
                        reference=c.id[:8],
                        libelle=c.intitule,
                        date_limite=c.prochaine_execution,
                        jours_restants=j,
                    )
                )
    echeances.sort(key=lambda e: e.date_limite)

    alertes: list[str] = []
    if sans_controle:
        alertes.append(f"{len(sans_controle)} obligation(s) active(s) sans contrôle rattaché.")
    if en_retard:
        alertes.append(f"{len(en_retard)} contrôle(s) en retard d'exécution.")
    if par_gravite["critique"]:
        alertes.append(f"{par_gravite['critique']} constat(s) critique(s) ouvert(s).")

    return SyntheseConformite(
        nb_obligations=len(obs),
        nb_obligations_actives=len(actives),
        nb_obligations_sans_controle=len(sans_controle),
        taux_couverture=_pct(len(actives) - len(sans_controle), len(actives)),
        nb_controls=len(ctrls),
        nb_controls_en_retard=len(en_retard),
        nb_findings=len(finds),
        nb_findings_ouverts=len(ouverts),
        taux_conformite=_pct(len(resolus), len(finds)) if finds else Decimal("100"),
        findings_ouverts_par_gravite=par_gravite,
        obligations_par_domaine=par_domaine,
        echeances=echeances,
        alertes=alertes,
    )
