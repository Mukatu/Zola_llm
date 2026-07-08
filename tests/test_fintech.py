"""Tests des moteurs Fintech déterministes — scoring crédit et KYC/AML."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from zolaos.agents.fintech.kyc import (
    AmlBareme,
    KycProfile,
    Transaction,
    evaluate_aml,
    evaluate_kyc,
)
from zolaos.agents.fintech.scoring import CreditRequest, score_credit

# --- Scoring crédit ---------------------------------------------------------


def test_score_bon_dossier_accorde() -> None:
    req = CreditRequest(
        revenu_mensuel_xaf=Decimal("800000"),
        charges_mensuelles_xaf=Decimal("100000"),
        montant_demande_xaf=Decimal("1500000"),
        duree_mois=24,
        anciennete_activite_mois=36,
        incidents_paiement=0,
        epargne_xaf=Decimal("400000"),
        garanties_xaf=Decimal("1500000"),
        type_emploi="salarie_public",
    )
    r = score_credit(req)
    assert r.decision == "accorde"
    assert r.grade in {"A", "B"}
    assert r.score >= 70
    assert r.mensualite_estimee_xaf > 0
    assert r.montant_max_suggere_xaf > 0
    # Explicabilité : un facteur par critère.
    assert {f.code for f in r.facteurs} == {
        "capacite",
        "anciennete",
        "incidents",
        "apport",
        "garanties",
        "stabilite",
    }
    assert r.bareme_indicatif is True


def test_score_endettement_excessif_refuse() -> None:
    """Charges + mensualité > plafond indicatif → refus automatique."""
    req = CreditRequest(
        revenu_mensuel_xaf=Decimal("200000"),
        charges_mensuelles_xaf=Decimal("150000"),
        montant_demande_xaf=Decimal("2000000"),
        duree_mois=12,
        anciennete_activite_mois=6,
        type_emploi="informel",
    )
    r = score_credit(req)
    assert r.decision == "refuse"
    assert r.taux_endettement_pct > Decimal("70")
    assert any("endettement" in a.lower() for a in r.avertissements)


def test_score_incidents_refus_automatique() -> None:
    req = CreditRequest(
        revenu_mensuel_xaf=Decimal("1000000"),
        charges_mensuelles_xaf=Decimal("50000"),
        montant_demande_xaf=Decimal("500000"),
        duree_mois=12,
        anciennete_activite_mois=48,
        incidents_paiement=6,
        garanties_xaf=Decimal("1000000"),
        type_emploi="salarie_prive",
    )
    r = score_credit(req)
    assert r.decision == "refuse"


def test_score_revenu_nul_inelligible() -> None:
    req = CreditRequest(
        revenu_mensuel_xaf=Decimal("0"),
        montant_demande_xaf=Decimal("100000"),
        duree_mois=6,
    )
    r = score_credit(req)
    assert r.decision == "refuse"
    assert r.capacite_remboursement_xaf == Decimal("0")


# --- KYC --------------------------------------------------------------------


def test_kyc_particulier_complet() -> None:
    p = KycProfile(
        nom="Jean Mabiala",
        type_client="particulier",
        pieces_fournies=["piece_identite", "justificatif_domicile"],
    )
    r = evaluate_kyc(p)
    assert r.complet is True
    assert r.pieces_manquantes == []
    assert r.niveau_risque == "faible"
    assert r.vigilance == "standard"
    assert r.peut_entrer_en_relation is True


def test_kyc_incomplet_bloque() -> None:
    p = KycProfile(nom="X", type_client="entreprise", pieces_fournies=["rccm"])
    r = evaluate_kyc(p)
    assert r.complet is False
    assert set(r.pieces_manquantes) == {"niu", "statuts", "piece_dirigeant"}
    assert r.peut_entrer_en_relation is False


def test_kyc_pep_vigilance_renforcee() -> None:
    p = KycProfile(
        nom="Ministre X",
        type_client="particulier",
        pieces_fournies=["piece_identite", "justificatif_domicile"],
        pep=True,
    )
    r = evaluate_kyc(p)
    assert r.vigilance == "renforcee"
    assert r.peut_entrer_en_relation is True  # complet, PEP ≠ blocage


def test_kyc_sanctions_bloque() -> None:
    p = KycProfile(
        nom="Y",
        pieces_fournies=["piece_identite", "justificatif_domicile"],
        correspondance_liste=True,
    )
    r = evaluate_kyc(p)
    assert r.niveau_risque == "eleve"
    assert r.peut_entrer_en_relation is False
    assert any("sanction" in m.lower() for m in r.motifs_blocage)


# --- AML --------------------------------------------------------------------


def test_aml_seuil_unitaire() -> None:
    txs = [Transaction(date=date(2026, 7, 1), montant_xaf=Decimal("6000000"), canal="especes")]
    r = evaluate_aml(txs)
    assert any(a.code == "seuil_unitaire" for a in r.alertes)


def test_aml_structuration() -> None:
    # 3 opérations juste sous le seuil (5M) → suspicion de fractionnement.
    txs = [
        Transaction(date=date(2026, 7, d), montant_xaf=Decimal("4800000"), canal="virement")
        for d in (1, 2, 3)
    ]
    r = evaluate_aml(txs)
    assert any(a.code == "structuration" for a in r.alertes)


def test_aml_especes_cumul() -> None:
    txs = [
        Transaction(date=date(2026, 7, d), montant_xaf=Decimal("4000000"), canal="especes")
        for d in (1, 2, 3)
    ]
    r = evaluate_aml(txs)
    assert r.volume_especes_xaf == Decimal("12000000")
    assert any(a.code in {"especes_intenses", "structuration"} for a in r.alertes)


def test_aml_ras() -> None:
    txs = [Transaction(date=date(2026, 7, 1), montant_xaf=Decimal("100000"), canal="virement")]
    r = evaluate_aml(txs)
    assert len(r.alertes) == 1
    assert r.alertes[0].code == "ras"


def test_aml_bareme_personnalise() -> None:
    bareme = AmlBareme(seuil_declaration_xaf=Decimal("1000000"))
    txs = [Transaction(date=date(2026, 7, 1), montant_xaf=Decimal("1200000"))]
    r = evaluate_aml(txs, bareme)
    assert any(a.code == "seuil_unitaire" for a in r.alertes)
