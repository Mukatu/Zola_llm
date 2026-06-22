"""Tests des endpoints déterministes ERP (/v1/erp/*) via TestClient (profil box)."""

from __future__ import annotations


def test_payroll_compute_requires_validation(client) -> None:  # type: ignore[no-untyped-def]
    # Barème seed non validé → 409 sans allow_unvalidated
    r = client.post("/v1/erp/payroll/compute", json={"brut_mensuel_xaf": "150000"})
    assert r.status_code == 409
    # Simulation explicite → OK
    r2 = client.post("/v1/erp/payroll/compute", json={"brut_mensuel_xaf": "150000", "allow_unvalidated": True})
    assert r2.status_code == 200
    body = r2.json()
    assert body["brut_xaf"] == "150000"  # Decimal sérialisé en chaîne (précision monétaire)
    assert "net_a_payer_xaf" in body
    assert body["barème_validé"] is False


def test_compta_validate_balanced(client) -> None:  # type: ignore[no-untyped-def]
    entry = {
        "date_ecriture": "2026-01-05", "journal": "VT", "libelle": "Vente",
        "lignes": [
            {"compte": "411", "libelle": "Client", "debit_xaf": "1180", "credit_xaf": "0"},
            {"compte": "701", "libelle": "Vente", "debit_xaf": "0", "credit_xaf": "1000"},
            {"compte": "4431", "libelle": "TVA", "debit_xaf": "0", "credit_xaf": "180"},
        ],
    }
    r = client.post("/v1/erp/compta/validate", json=entry)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_compta_validate_unbalanced(client) -> None:  # type: ignore[no-untyped-def]
    entry = {
        "date_ecriture": "2026-01-05", "journal": "VT", "libelle": "X",
        "lignes": [
            {"compte": "411", "libelle": "Client", "debit_xaf": "1180", "credit_xaf": "0"},
            {"compte": "701", "libelle": "Vente", "debit_xaf": "0", "credit_xaf": "900"},
        ],
    }
    r = client.post("/v1/erp/compta/validate", json=entry)
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_supply_analyze(client) -> None:  # type: ignore[no-untyped-def]
    payload = {"items": [
        {"sku": "A", "libelle": "Gants", "quantite_actuelle": "10", "conso_moyenne_jour": "2",
         "delai_appro_jours": 5, "stock_securite": "4"},
        {"sku": "B", "libelle": "Stock plein", "quantite_actuelle": "1000", "conso_moyenne_jour": "1",
         "delai_appro_jours": 3},
    ]}
    r = client.post("/v1/erp/supply/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    skus = {s["sku"] for s in body["suggestions"]}
    assert skus == {"A"}
    assert body["suggestions"][0]["urgence"] == "high"


def test_achats_compare(client) -> None:  # type: ignore[no-untyped-def]
    payload = {"offres": [
        {"id_externe": "O1", "fournisseur": "Alpha", "objet": "x", "montant_ht_xaf": "1000000", "montant_ttc_xaf": "1000000", "delai_livraison_jours": 10},
        {"id_externe": "O2", "fournisseur": "Beta", "objet": "x", "montant_ht_xaf": "800000", "montant_ttc_xaf": "800000", "delai_livraison_jours": 5},
    ]}
    r = client.post("/v1/erp/achats/compare", json=payload)
    assert r.status_code == 200
    assert r.json()["classement"][0]["fournisseur"] == "Beta"


def test_hse_cartographie(client) -> None:  # type: ignore[no-untyped-def]
    payload = {"risques": [
        {"id_externe": "R1", "libelle": "Incendie", "probabilite": 2, "gravite": 2},
        {"id_externe": "R2", "libelle": "Électrocution", "probabilite": 5, "gravite": 4},
    ]}
    r = client.post("/v1/erp/hse/cartographie", json=payload)
    assert r.status_code == 200
    carto = r.json()["risques"]
    assert carto[0]["reference"] == "R2"
    assert carto[0]["niveau"] == "critique"
