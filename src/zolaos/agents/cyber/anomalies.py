"""Détection d'anomalies sur journaux — déterministe, **défensive** (CYBER-2).

Analyse un lot d'événements de journalisation **déclarés/importés** (pas de
collecte active, pas de sonde réseau) et dérive des signaux de vigilance par
règles déterministes paramétrables (indicatives) : force brute, succès après
échecs répétés, accès hors horaires, multiplicité d'adresses IP, changements de
privilèges/configuration. Le moteur agrège les faits fournis ; il n'exécute
aucune action et ne fabrique aucune donnée. Le LLM ne fait que narrer/prioriser.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

TypeEvenement = Literal[
    "auth_success", "auth_failure", "access", "privilege_change", "config_change"
]
Niveau = Literal["alerte", "attention", "info"]

_RANG_NIVEAU: dict[str, int] = {"info": 0, "attention": 1, "alerte": 2}


class LogEvent(BaseModel):
    model_config = {"extra": "forbid"}

    horodatage: datetime
    type: TypeEvenement
    utilisateur: str = ""
    source_ip: str = ""
    ressource: str = ""


class ParamsDetection(BaseModel):
    """Seuils **indicatifs** et paramétrables (jamais normatifs)."""

    model_config = {"extra": "forbid"}

    fenetre_minutes: int = 15
    seuil_echecs: int = 5  # échecs d'auth dans la fenêtre → force brute
    heure_ouverture: int = 7  # accès avant/après → hors horaires
    heure_fermeture: int = 20
    seuil_ips_par_user: int = 3  # nombre d'IP distinctes par utilisateur


class Anomalie(BaseModel):
    code: str
    niveau: Niveau
    titre: str
    detail: str
    entite: str = ""  # utilisateur ou IP concernée
    occurrences: int = 0


class AnalyseAnomalies(BaseModel):
    nb_events: int
    nb_echecs_auth: int
    nb_succes_auth: int
    nb_ip_distinctes: int
    nb_utilisateurs: int
    periode_debut: datetime | None = None
    periode_fin: datetime | None = None
    niveau: str  # sévérité max (ou "aucun")
    anomalies: list[Anomalie]
    reference_cadre: str


def _max_dans_fenetre(horodatages: list[datetime], fenetre: timedelta) -> int:
    """Nombre maximal d'horodatages tenant dans une fenêtre glissante (deux pointeurs)."""
    ts = sorted(horodatages)
    debut = 0
    maxi = 0
    for fin in range(len(ts)):
        while ts[fin] - ts[debut] > fenetre:
            debut += 1
        maxi = max(maxi, fin - debut + 1)
    return maxi


def detecter_anomalies(
    events: Iterable[LogEvent], params: ParamsDetection | None = None
) -> AnalyseAnomalies:
    """Dérive les anomalies d'un lot d'événements (déterministe, défensif)."""
    p = params or ParamsDetection()
    evs = list(events)
    fenetre = timedelta(minutes=p.fenetre_minutes)

    echecs = [e for e in evs if e.type == "auth_failure"]
    succes = [e for e in evs if e.type == "auth_success"]
    ips = {e.source_ip for e in evs if e.source_ip}
    users = {e.utilisateur for e in evs if e.utilisateur}

    anomalies: list[Anomalie] = []

    # 1) Force brute par IP puis par utilisateur (échecs rapprochés).
    extracteurs = (("ip", lambda e: e.source_ip), ("utilisateur", lambda e: e.utilisateur))
    for cle, getter in extracteurs:
        groupes: dict[str, list[datetime]] = defaultdict(list)
        for e in echecs:
            k = getter(e)
            if k:
                groupes[k].append(e.horodatage)
        for entite, horodatages in groupes.items():
            pic = _max_dans_fenetre(horodatages, fenetre)
            if pic >= p.seuil_echecs:
                anomalies.append(
                    Anomalie(
                        code=f"force_brute_{cle}",
                        niveau="alerte",
                        titre=f"Rafale d'échecs d'authentification ({cle})",
                        detail=(
                            f"{pic} échecs en ≤ {p.fenetre_minutes} min pour {entite} : "
                            "tentative de force brute possible. Vérifier et bloquer si besoin."
                        ),
                        entite=entite,
                        occurrences=pic,
                    )
                )

    # 2) Succès après une rafale d'échecs pour le même utilisateur (compromission possible).
    echecs_user: dict[str, list[datetime]] = defaultdict(list)
    for e in echecs:
        if e.utilisateur:
            echecs_user[e.utilisateur].append(e.horodatage)
    for s in succes:
        if not s.utilisateur:
            continue
        recents = [
            t
            for t in echecs_user.get(s.utilisateur, [])
            if s.horodatage - fenetre <= t <= s.horodatage
        ]
        if len(recents) >= p.seuil_echecs:
            anomalies.append(
                Anomalie(
                    code="succes_apres_echecs",
                    niveau="alerte",
                    titre="Connexion réussie après des échecs répétés",
                    detail=(
                        f"{len(recents)} échecs puis un succès pour {s.utilisateur} : "
                        "compte potentiellement compromis. Réinitialiser et enquêter."
                    ),
                    entite=s.utilisateur,
                    occurrences=len(recents),
                )
            )

    # 3) Accès hors horaires ouvrés.
    hors = [
        e for e in evs if e.horodatage.hour < p.heure_ouverture or e.horodatage.hour >= p.heure_fermeture
    ]
    if hors:
        anomalies.append(
            Anomalie(
                code="hors_horaires",
                niveau="attention",
                titre="Activité hors des horaires ouvrés",
                detail=(
                    f"{len(hors)} événement(s) hors de la plage "
                    f"{p.heure_ouverture}h–{p.heure_fermeture}h. À corréler avec l'activité attendue."
                ),
                occurrences=len(hors),
            )
        )

    # 4) Multiplicité d'adresses IP pour un même utilisateur.
    ips_par_user: dict[str, set[str]] = defaultdict(set)
    for e in evs:
        if e.utilisateur and e.source_ip:
            ips_par_user[e.utilisateur].add(e.source_ip)
    for user, ensemble in ips_par_user.items():
        if len(ensemble) >= p.seuil_ips_par_user:
            anomalies.append(
                Anomalie(
                    code="ip_multiples",
                    niveau="attention",
                    titre="Utilisateur connecté depuis plusieurs adresses",
                    detail=(
                        f"{len(ensemble)} adresses IP distinctes pour {user} : "
                        "vérifier la légitimité (déplacement, VPN, partage de compte)."
                    ),
                    entite=user,
                    occurrences=len(ensemble),
                )
            )

    # 5) Changements de privilèges / de configuration à revoir.
    for typ, code, titre in (
        ("privilege_change", "changements_privileges", "Changements de privilèges à revoir"),
        ("config_change", "changements_config", "Modifications de configuration à revoir"),
    ):
        n = sum(1 for e in evs if e.type == typ)
        if n:
            anomalies.append(
                Anomalie(
                    code=code,
                    niveau="info",
                    titre=titre,
                    detail=f"{n} événement(s) de type {typ} : passer en revue (traçabilité).",
                    occurrences=n,
                )
            )

    pire = max((_RANG_NIVEAU[a.niveau] for a in anomalies), default=-1)
    niveau = next((k for k, v in _RANG_NIVEAU.items() if v == pire), "aucun") if pire >= 0 else "aucun"
    anomalies.sort(key=lambda a: -_RANG_NIVEAU[a.niveau])

    horodatages = [e.horodatage for e in evs]
    return AnalyseAnomalies(
        nb_events=len(evs),
        nb_echecs_auth=len(echecs),
        nb_succes_auth=len(succes),
        nb_ip_distinctes=len(ips),
        nb_utilisateurs=len(users),
        periode_debut=min(horodatages) if horodatages else None,
        periode_fin=max(horodatages) if horodatages else None,
        niveau=niveau,
        anomalies=anomalies,
        reference_cadre=(
            "Détection déterministe indicative (analyse de journaux déclarés) — défensive, "
            "seuils à adapter ; ne remplace pas un SIEM ni une investigation formelle."
        ),
    )
