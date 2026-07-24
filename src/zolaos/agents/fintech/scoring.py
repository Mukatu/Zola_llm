"""Scoring de crédit **déterministe et explicable** (microfinance / EMF, CG).

Le score agrège des facteurs pondérés (capacité de remboursement, ancienneté,
historique d'incidents, apport, garanties, stabilité) — chaque facteur est
restitué (sens, poids, commentaire) pour une décision transparente, jamais une
boîte noire. Le calcul de mensualité utilise un taux **indicatif paramétrable**
(aucun taux d'usure légal n'est affirmé). Le résultat est une **aide à la
décision** : l'octroi reste soumis à l'analyse humaine de l'agent de crédit.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")
_CENT = Decimal("100")
_Q = Decimal("1")


class ScoringBareme(BaseModel):
    """Paramètres du modèle de score — **indicatifs**, ajustables par l'EMF.

    ``indicatif=True`` rappelle que ces valeurs ne sont pas des normes légales
    figées : elles sont paramétrables et doivent être calibrées/validées.
    """

    indicatif: bool = True
    taux_endettement_max: Decimal = Decimal("0.33")  # norme prudentielle indicative
    taux_endettement_refus: Decimal = Decimal("0.70")  # au-delà → refus automatique
    incidents_refus: int = 5  # nb d'incidents → refus automatique
    apport_cible: Decimal = Decimal("0.20")  # apport pour crédit « plein »
    anciennete_cible_mois: int = 24
    taux_annuel_indicatif: Decimal = Decimal("0.18")  # pour estimer la mensualité
    # Pondérations (somme = 100).
    poids_capacite: Decimal = Decimal("35")
    poids_anciennete: Decimal = Decimal("15")
    poids_incidents: Decimal = Decimal("20")
    poids_apport: Decimal = Decimal("12")
    poids_garanties: Decimal = Decimal("10")
    poids_stabilite: Decimal = Decimal("8")
    # Seuils de décision (score sur 100).
    seuil_accord: int = 70
    seuil_etude: int = 50


BAREME_DEFAUT = ScoringBareme()

# Stabilité de la source de revenu (facteur 0..1).
_STABILITE_EMPLOI = {
    "salarie_public": Decimal("1.0"),
    "salarie_prive": Decimal("0.85"),
    "independant": Decimal("0.60"),
    "informel": Decimal("0.40"),
}


class CreditRequest(BaseModel):
    """Dossier de demande de crédit (données fournies par l'agent de crédit)."""

    revenu_mensuel_xaf: Decimal = Field(ge=0)
    charges_mensuelles_xaf: Decimal = Field(default=_ZERO, ge=0)  # dettes/loyer existants
    montant_demande_xaf: Decimal = Field(gt=0)
    duree_mois: int = Field(gt=0, le=120)
    anciennete_activite_mois: int = Field(default=0, ge=0)
    incidents_paiement: int = Field(default=0, ge=0)  # incidents passés connus
    epargne_xaf: Decimal = Field(default=_ZERO, ge=0)  # apport / épargne
    garanties_xaf: Decimal = Field(default=_ZERO, ge=0)  # valeur des garanties
    flux_mobile_money_mensuel_xaf: Decimal | None = Field(default=None, ge=0)
    type_emploi: str = "informel"


class Facteur(BaseModel):
    """Contribution explicable d'un facteur au score."""

    code: str
    libelle: str
    sens: str  # positif | negatif | neutre
    valeur: str  # valeur lisible (ex. « 41 % »)
    contribution: int  # points apportés (sur le poids du facteur)
    commentaire: str


class CreditScore(BaseModel):
    score: int  # 0..100
    grade: str  # A..E
    decision: str  # accorde | a_etudier | refuse
    taux_endettement_pct: Decimal
    capacite_remboursement_xaf: Decimal  # mensualité soutenable
    mensualite_estimee_xaf: Decimal  # pour le montant demandé
    montant_max_suggere_xaf: Decimal
    cout_total_credit_xaf: Decimal
    facteurs: list[Facteur]
    avertissements: list[str]
    bareme_indicatif: bool


def _q0(v: Decimal) -> Decimal:
    return v.quantize(_Q, rounding=ROUND_HALF_UP)


def _mensualite(principal: Decimal, taux_mensuel: Decimal, n: int) -> Decimal:
    """Mensualité d'un amortissement constant (annuité)."""
    if principal <= 0 or n <= 0:
        return _ZERO
    if taux_mensuel <= 0:
        return _q0(principal / Decimal(n))
    facteur = (Decimal(1) + taux_mensuel) ** n
    return _q0(principal * taux_mensuel * facteur / (facteur - Decimal(1)))


def _principal_max(mensualite: Decimal, taux_mensuel: Decimal, n: int) -> Decimal:
    """Principal maximal finançable pour une mensualité soutenable (inverse annuité)."""
    if mensualite <= 0 or n <= 0:
        return _ZERO
    if taux_mensuel <= 0:
        return _q0(mensualite * Decimal(n))
    facteur = (Decimal(1) + taux_mensuel) ** n
    return _q0(mensualite * (facteur - Decimal(1)) / (taux_mensuel * facteur))


def _grade(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def score_credit(req: CreditRequest, bareme: ScoringBareme | None = None) -> CreditScore:
    """Calcule le score de crédit (déterministe) et la décision recommandée."""
    b = bareme or BAREME_DEFAUT
    taux_mensuel = (b.taux_annuel_indicatif / Decimal("12")).quantize(Decimal("0.000001"))
    revenu = req.revenu_mensuel_xaf
    avert: list[str] = []
    facteurs: list[Facteur] = []

    mensualite = _mensualite(req.montant_demande_xaf, taux_mensuel, req.duree_mois)
    charges_totales = req.charges_mensuelles_xaf + mensualite
    taux_endettement = (charges_totales / revenu) if revenu > 0 else Decimal("9")
    taux_pct = _q0(taux_endettement * _CENT) if revenu > 0 else Decimal("999")

    # Capacité de remboursement soutenable (mensualité max) selon le taux prudentiel.
    capacite = revenu * b.taux_endettement_max - req.charges_mensuelles_xaf
    capacite = capacite if capacite > 0 else _ZERO
    montant_max = _principal_max(capacite, taux_mensuel, req.duree_mois)

    # 1) Capacité (taux d'endettement après octroi).
    if taux_endettement <= b.taux_endettement_max:
        f_cap = Decimal(1)
    elif taux_endettement >= b.taux_endettement_refus:
        f_cap = _ZERO
    else:
        span = b.taux_endettement_refus - b.taux_endettement_max
        f_cap = (b.taux_endettement_refus - taux_endettement) / span
    facteurs.append(
        Facteur(
            code="capacite",
            libelle="Capacité de remboursement",
            sens="positif" if f_cap >= Decimal("0.5") else "negatif",
            valeur=f"taux d'endettement {taux_pct} %",
            contribution=int(_q0(f_cap * b.poids_capacite)),
            commentaire=f"Seuil prudentiel indicatif : {int(b.taux_endettement_max * 100)} %.",
        )
    )

    # 2) Ancienneté de l'activité.
    f_anc = min(
        Decimal(1), Decimal(req.anciennete_activite_mois) / Decimal(b.anciennete_cible_mois)
    )
    facteurs.append(
        Facteur(
            code="anciennete",
            libelle="Ancienneté de l'activité",
            sens="positif" if f_anc >= Decimal("0.5") else "negatif",
            valeur=f"{req.anciennete_activite_mois} mois",
            contribution=int(_q0(f_anc * b.poids_anciennete)),
            commentaire=f"Cible : {b.anciennete_cible_mois} mois.",
        )
    )

    # 3) Historique d'incidents.
    if req.incidents_paiement == 0:
        f_inc = Decimal(1)
    elif req.incidents_paiement <= 2:
        f_inc = Decimal("0.6")
    elif req.incidents_paiement <= 4:
        f_inc = Decimal("0.2")
    else:
        f_inc = _ZERO
    facteurs.append(
        Facteur(
            code="incidents",
            libelle="Historique de remboursement",
            sens="positif" if req.incidents_paiement == 0 else "negatif",
            valeur=f"{req.incidents_paiement} incident(s)",
            contribution=int(_q0(f_inc * b.poids_incidents)),
            commentaire=(
                "Aucun incident connu." if req.incidents_paiement == 0 else "Incidents passés."
            ),
        )
    )

    # 4) Apport / épargne.
    ratio_apport = (
        (req.epargne_xaf / req.montant_demande_xaf) if req.montant_demande_xaf > 0 else _ZERO
    )
    f_app = min(Decimal(1), ratio_apport / b.apport_cible) if b.apport_cible > 0 else _ZERO
    facteurs.append(
        Facteur(
            code="apport",
            libelle="Apport / épargne",
            sens="positif" if f_app >= Decimal("0.5") else "neutre",
            valeur=f"{_q0(ratio_apport * _CENT)} % du montant",
            contribution=int(_q0(f_app * b.poids_apport)),
            commentaire=f"Apport cible : {int(b.apport_cible * 100)} %.",
        )
    )

    # 5) Garanties.
    couv = (req.garanties_xaf / req.montant_demande_xaf) if req.montant_demande_xaf > 0 else _ZERO
    f_gar = min(Decimal(1), couv)
    facteurs.append(
        Facteur(
            code="garanties",
            libelle="Garanties",
            sens="positif" if f_gar >= Decimal("0.5") else "neutre",
            valeur=f"{_q0(couv * _CENT)} % de couverture",
            contribution=int(_q0(f_gar * b.poids_garanties)),
            commentaire="Couverture du montant par les garanties.",
        )
    )

    # 6) Stabilité (type d'emploi + régularité Mobile Money).
    f_stab = _STABILITE_EMPLOI.get(req.type_emploi, Decimal("0.4"))
    if req.flux_mobile_money_mensuel_xaf and req.flux_mobile_money_mensuel_xaf > 0:
        f_stab = min(Decimal(1), f_stab + Decimal("0.15"))
    facteurs.append(
        Facteur(
            code="stabilite",
            libelle="Stabilité des revenus",
            sens="positif" if f_stab >= Decimal("0.6") else "negatif",
            valeur=req.type_emploi,
            contribution=int(_q0(f_stab * b.poids_stabilite)),
            commentaire=(
                "Bonus régularité Mobile Money."
                if req.flux_mobile_money_mensuel_xaf
                else "Source de revenu."
            ),
        )
    )

    score = min(100, sum(f.contribution for f in facteurs))

    # Règles dures (refus automatique) — priment sur le score.
    refus_auto = False
    if revenu <= 0:
        refus_auto = True
        avert.append("Revenu déclaré nul : dossier inéligible en l'état.")
    if taux_endettement > b.taux_endettement_refus:
        refus_auto = True
        avert.append(
            f"Taux d'endettement {taux_pct} % au-delà du plafond indicatif "
            f"{int(b.taux_endettement_refus * 100)} %."
        )
    if req.incidents_paiement >= b.incidents_refus:
        refus_auto = True
        avert.append(f"{req.incidents_paiement} incidents : au-delà du seuil de refus.")
    if capacite <= 0:
        avert.append("Capacité de remboursement nulle après charges : montant à revoir.")

    if refus_auto:
        decision = "refuse"
    elif score >= b.seuil_accord:
        decision = "accorde"
    elif score >= b.seuil_etude:
        decision = "a_etudier"
    else:
        decision = "refuse"

    if montant_max < req.montant_demande_xaf and decision != "refuse":
        avert.append(
            f"Montant demandé ({_q0(req.montant_demande_xaf)} XAF) supérieur au montant "
            f"soutenable estimé ({montant_max} XAF) : envisager une réduction ou un allongement."
        )

    cout_total = _q0(mensualite * Decimal(req.duree_mois) - req.montant_demande_xaf)
    cout_total = cout_total if cout_total > 0 else _ZERO

    return CreditScore(
        score=score,
        grade=_grade(score),
        decision=decision,
        taux_endettement_pct=taux_pct,
        capacite_remboursement_xaf=_q0(capacite),
        mensualite_estimee_xaf=mensualite,
        montant_max_suggere_xaf=montant_max,
        cout_total_credit_xaf=cout_total,
        facteurs=facteurs,
        avertissements=avert,
        bareme_indicatif=b.indicatif,
    )
