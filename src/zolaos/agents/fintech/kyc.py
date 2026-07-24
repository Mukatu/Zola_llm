"""KYC (connaissance client) & AML/LBC-FT — contrôles **déterministes**.

- **KYC** : complétude documentaire (par type de client), niveau de risque et
  degré de vigilance (standard / renforcée), éligibilité à l'entrée en relation.
- **AML** : détection déterministe d'opérations à signaler — dépassement de
  seuil, **structuration** (fractionnement sous le seuil), intensité en espèces.

Cadre : LBC-FT CEMAC / **GABAC**. Les seuils sont des **constantes indicatives
paramétrables** (jamais affirmées comme des montants légaux figés) ; toute alerte
est une **aide à la vigilance**, pas une qualification juridique. Les données
personnelles relèvent de la Loi 29-2019 (protection des données, CG).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

_ZERO = Decimal("0")

# Pièces requises par type de client (paramétrable).
PIECES_REQUISES = {
    "particulier": ("piece_identite", "justificatif_domicile"),
    "entreprise": ("rccm", "niu", "statuts", "piece_dirigeant"),
}

# Secteurs à risque accru (indicatif — vigilance renforcée usuelle).
SECTEURS_RISQUE = {
    "change_manuel",
    "immobilier",
    "négoce_matieres_premieres",
    "jeux_paris",
    "transfert_fonds",
    "or_metaux_precieux",
}

# Seuils AML indicatifs (paramétrables) — à confirmer (GABAC / CEMAC).
SEUIL_DECLARATION_XAF = Decimal("5000000")  # opération unitaire — INDICATIF
SEUIL_STRUCTURATION_RATIO = Decimal("0.90")  # « juste sous le seuil » ≥ 90 %
STRUCTURATION_MIN_OPS = 3  # nb d'opérations rapprochées pour suspicion
SEUIL_ESPECES_CUMUL_XAF = Decimal("10000000")  # cumul espèces sur la période — INDICATIF


class KycProfile(BaseModel):
    nom: str
    type_client: str = "particulier"  # particulier | entreprise
    pieces_fournies: list[str] = Field(default_factory=list)
    pep: bool = False  # personne politiquement exposée
    pays_residence: str = "CG"
    secteur_activite: str | None = None
    correspondance_liste: bool = False  # concordance liste de sanctions (fournie)


class KycResult(BaseModel):
    complet: bool
    pieces_manquantes: list[str]
    niveau_risque: str  # faible | moyen | eleve
    score_risque: int
    facteurs_risque: list[str]
    vigilance: str  # standard | renforcee
    peut_entrer_en_relation: bool
    motifs_blocage: list[str]
    reference_cadre: str


def evaluate_kyc(profile: KycProfile) -> KycResult:
    """Évalue la complétude KYC, le niveau de risque et la vigilance requise."""
    requises = PIECES_REQUISES.get(profile.type_client, PIECES_REQUISES["particulier"])
    fournies = {p.strip().lower() for p in profile.pieces_fournies}
    manquantes = [p for p in requises if p not in fournies]
    complet = not manquantes

    score = 0
    facteurs: list[str] = []
    if profile.pep:
        score += 40
        facteurs.append("Personne politiquement exposée (PEP).")
    if profile.correspondance_liste:
        score += 60
        facteurs.append("Concordance avec une liste de sanctions/surveillance.")
    if profile.secteur_activite and profile.secteur_activite.lower() in SECTEURS_RISQUE:
        score += 25
        facteurs.append(f"Secteur à risque accru : {profile.secteur_activite}.")
    if profile.pays_residence.upper() != "CG":
        score += 15
        facteurs.append(f"Résidence hors CG : {profile.pays_residence}.")
    if not complet:
        score += 10
        facteurs.append("Dossier incomplet.")

    if score >= 50:
        niveau = "eleve"
    elif score >= 20:
        niveau = "moyen"
    else:
        niveau = "faible"

    vigilance = "renforcee" if (profile.pep or niveau == "eleve") else "standard"

    # Blocages : concordance sanctions ou dossier incomplet → pas d'entrée en relation.
    motifs: list[str] = []
    if profile.correspondance_liste:
        motifs.append(
            "Concordance liste de sanctions : entrée en relation à bloquer (revue conformité)."
        )
    if not complet:
        motifs.append("Pièces obligatoires manquantes.")
    peut_entrer = not motifs

    if not facteurs:
        facteurs.append("Aucun facteur de risque particulier détecté.")

    return KycResult(
        complet=complet,
        pieces_manquantes=manquantes,
        niveau_risque=niveau,
        score_risque=min(100, score),
        facteurs_risque=facteurs,
        vigilance=vigilance,
        peut_entrer_en_relation=peut_entrer,
        motifs_blocage=motifs,
        reference_cadre="LBC-FT CEMAC/GABAC — vigilance indicative, à confirmer.",
    )


class Transaction(BaseModel):
    date: date
    montant_xaf: Decimal = Field(gt=0)
    sens: str = "entree"  # entree | sortie
    canal: str = "virement"  # especes | virement | mobile_money
    contrepartie: str | None = None


class AmlAlert(BaseModel):
    code: str
    niveau: str  # info | attention | alerte
    titre: str
    detail: str


class AmlBareme(BaseModel):
    indicatif: bool = True
    seuil_declaration_xaf: Decimal = SEUIL_DECLARATION_XAF
    seuil_especes_cumul_xaf: Decimal = SEUIL_ESPECES_CUMUL_XAF
    structuration_ratio: Decimal = SEUIL_STRUCTURATION_RATIO
    structuration_min_ops: int = STRUCTURATION_MIN_OPS


class AmlResult(BaseModel):
    nb_operations: int
    volume_total_xaf: Decimal
    volume_especes_xaf: Decimal
    alertes: list[AmlAlert]
    bareme_indicatif: bool
    reference_cadre: str


def _fmt(v: Decimal) -> str:
    return f"{v:,.0f}".replace(",", " ")


def evaluate_aml(transactions: list[Transaction], bareme: AmlBareme | None = None) -> AmlResult:
    """Détecte des motifs de vigilance AML (déterministe) sur un lot d'opérations."""
    b = bareme or AmlBareme()
    alertes: list[AmlAlert] = []
    volume = sum((t.montant_xaf for t in transactions), _ZERO)
    especes = sum((t.montant_xaf for t in transactions if t.canal == "especes"), _ZERO)

    # 1) Dépassement de seuil unitaire.
    for t in transactions:
        if t.montant_xaf >= b.seuil_declaration_xaf:
            alertes.append(
                AmlAlert(
                    code="seuil_unitaire",
                    niveau="alerte",
                    titre="Opération au-delà du seuil indicatif",
                    detail=(
                        f"{_fmt(t.montant_xaf)} XAF le {t.date.isoformat()} "
                        f"({t.canal}) ≥ seuil {_fmt(b.seuil_declaration_xaf)} XAF. "
                        "Déclaration à envisager (à confirmer GABAC)."
                    ),
                )
            )

    # 2) Structuration : plusieurs opérations « juste sous » le seuil, cumul au-dessus.
    plancher = b.seuil_declaration_xaf * b.structuration_ratio
    proches = [t for t in transactions if plancher <= t.montant_xaf < b.seuil_declaration_xaf]
    if len(proches) >= b.structuration_min_ops:
        cumul = sum((t.montant_xaf for t in proches), _ZERO)
        alertes.append(
            AmlAlert(
                code="structuration",
                niveau="alerte",
                titre="Fractionnement possible (structuration)",
                detail=(
                    f"{len(proches)} opérations juste sous le seuil "
                    f"(cumul {_fmt(cumul)} XAF) : fractionnement possible pour éviter la déclaration."
                ),
            )
        )

    # 3) Intensité espèces.
    if especes >= b.seuil_especes_cumul_xaf:
        alertes.append(
            AmlAlert(
                code="especes_intenses",
                niveau="attention",
                titre="Volume d'espèces élevé",
                detail=f"Cumul espèces {_fmt(especes)} XAF ≥ {_fmt(b.seuil_especes_cumul_xaf)} XAF.",
            )
        )

    if not alertes:
        alertes.append(
            AmlAlert(
                code="ras",
                niveau="info",
                titre="Aucun motif de vigilance",
                detail="Les opérations fournies ne déclenchent aucune alerte indicative.",
            )
        )

    return AmlResult(
        nb_operations=len(transactions),
        volume_total_xaf=volume,
        volume_especes_xaf=especes,
        alertes=alertes,
        bareme_indicatif=b.indicatif,
        reference_cadre="LBC-FT CEMAC/GABAC — seuils indicatifs à confirmer.",
    )
