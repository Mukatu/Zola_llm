"""Pilotage du portefeuille de crédit — agrégation **déterministe**.

Dérive des indicateurs de portefeuille des dossiers persistés : structure par
statut, encours décaissé, taux d'acceptation/décaissement, répartition du risque
par grade, service de la dette mensuel engagé, plus un volet KYC. Aucun chiffre
n'est inventé.

Limite assumée : le **PAR (Portfolio At Risk / impayés)** exige un échéancier de
remboursement et des paiements constatés — non persistés à ce stade. Il n'est
donc **pas** calculé (ce serait une valeur fabriquée) mais signalé comme suite.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel

_ZERO = Decimal("0")
_Q = Decimal("1")
_CENT = Decimal("100")

_STATUTS_CREDIT = ("evaluee", "accordee", "refusee", "decaissee", "cloturee")
_STATUTS_KYC = ("a_valider", "valide", "refuse")
_GRADES = ("A", "B", "C", "D", "E")
_ACCORDES = ("accordee", "decaissee")
_DECIDES = ("accordee", "refusee", "decaissee", "cloturee")


class PortfolioStats(BaseModel):
    nb_dossiers: int
    par_statut: dict[str, int]
    montant_demande_total_xaf: Decimal
    montant_accorde_xaf: Decimal
    encours_decaisse_xaf: Decimal
    service_dette_mensuel_xaf: Decimal
    taux_acceptation_pct: Decimal
    taux_decaissement_pct: Decimal
    score_moyen: int
    repartition_grade: dict[str, int]
    nb_kyc: int
    kyc_par_statut: dict[str, int]
    kyc_par_risque: dict[str, int]
    nb_vigilance_renforcee: int
    signaux: list[str]
    note: str


def _q0(v: Decimal) -> Decimal:
    return v.quantize(_Q, rounding=ROUND_HALF_UP)


def _pct(part: int, total: int) -> Decimal:
    if total <= 0:
        return _ZERO
    return (Decimal(part) / Decimal(total) * _CENT).quantize(_Q, rounding=ROUND_HALF_UP)


def portfolio_stats(
    apps: Sequence[Any], kyc: Sequence[Any]
) -> PortfolioStats:
    """Agrège les indicateurs de portefeuille (déterministe)."""
    par_statut = {s: 0 for s in _STATUTS_CREDIT}
    repartition = {g: 0 for g in _GRADES}
    montant_total = _ZERO
    montant_accorde = _ZERO
    encours = _ZERO
    service_dette = _ZERO
    somme_scores = 0

    for a in apps:
        statut = a.statut
        par_statut[statut] = par_statut.get(statut, 0) + 1
        montant_total += a.montant_demande_xaf
        somme_scores += a.score
        if statut in _ACCORDES:
            montant_accorde += a.montant_demande_xaf
            repartition[a.grade] = repartition.get(a.grade, 0) + 1
        if statut == "decaissee":
            encours += a.montant_demande_xaf
            service_dette += a.mensualite_xaf

    nb = len(apps)
    nb_decides = sum(par_statut.get(s, 0) for s in _DECIDES)
    nb_accordes = sum(par_statut.get(s, 0) for s in _ACCORDES)
    taux_acceptation = _pct(nb_accordes, nb_decides)
    taux_decaissement = _pct(par_statut.get("decaissee", 0), nb_accordes)
    score_moyen = round(somme_scores / nb) if nb else 0

    # Volet KYC.
    kyc_statut = {s: 0 for s in _STATUTS_KYC}
    kyc_risque: dict[str, int] = {"faible": 0, "moyen": 0, "eleve": 0}
    vigilance_renforcee = 0
    for k in kyc:
        kyc_statut[k.statut] = kyc_statut.get(k.statut, 0) + 1
        kyc_risque[k.niveau_risque] = kyc_risque.get(k.niveau_risque, 0) + 1
        if k.vigilance == "renforcee":
            vigilance_renforcee += 1

    # Signaux déterministes.
    signaux: list[str] = []
    nb_portefeuille = nb_accordes
    risque_eleve = repartition.get("D", 0) + repartition.get("E", 0)
    if nb_portefeuille and _pct(risque_eleve, nb_portefeuille) >= 30:
        signaux.append(
            f"Concentration de risque élevée : {risque_eleve}/{nb_portefeuille} "
            "dossiers du portefeuille en grade D/E."
        )
    if par_statut.get("evaluee", 0) >= 5:
        signaux.append(
            f"{par_statut['evaluee']} dossiers évalués en attente de décision."
        )
    if par_statut.get("accordee", 0) > 0:
        signaux.append(
            f"{par_statut['accordee']} dossier(s) accordé(s) non encore décaissé(s)."
        )
    if kyc_statut.get("a_valider", 0) >= 3:
        signaux.append(f"{kyc_statut['a_valider']} dossiers KYC à valider (conformité).")
    if not signaux:
        signaux.append("Aucun signal de pilotage particulier.")

    return PortfolioStats(
        nb_dossiers=nb,
        par_statut=par_statut,
        montant_demande_total_xaf=_q0(montant_total),
        montant_accorde_xaf=_q0(montant_accorde),
        encours_decaisse_xaf=_q0(encours),
        service_dette_mensuel_xaf=_q0(service_dette),
        taux_acceptation_pct=taux_acceptation,
        taux_decaissement_pct=taux_decaissement,
        score_moyen=score_moyen,
        repartition_grade=repartition,
        nb_kyc=len(kyc),
        kyc_par_statut=kyc_statut,
        kyc_par_risque=kyc_risque,
        nb_vigilance_renforcee=vigilance_renforcee,
        signaux=signaux,
        note=(
            "Le PAR (impayés) nécessite un échéancier de remboursement et des "
            "paiements constatés — non disponibles à ce stade."
        ),
    )
