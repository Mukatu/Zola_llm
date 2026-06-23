"""Tests des endpoints data déterministes (CRM, BI, Finance) via TestClient."""

from __future__ import annotations


def test_crm_analyze(client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "opportunities": [
            {
                "id_externe": "O1",
                "client": "ACME",
                "libelle": "Deal A",
                "montant_xaf": "1000000",
                "etape": "prospection",
            },
            {
                "id_externe": "O2",
                "client": "ACME",
                "libelle": "Deal B",
                "montant_xaf": "2000000",
                "etape": "negociation",
            },
            {
                "id_externe": "O3",
                "client": "ACME",
                "libelle": "Deal C",
                "montant_xaf": "3000000",
                "etape": "gagnee",
            },
        ],
        "quotes": [],
    }
    r = client.post("/v1/crm/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline"]["nb_open"] == 2
    assert body["pipeline"]["weighted_open_xaf"] == "1700000"
    assert "O2" in body["scores"]


def test_bi_kpis(client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "invoices": [
            {
                "id_externe": "I1",
                "numero": "F1",
                "sens": "vente",
                "tiers": "X",
                "date_emission": "2026-01-01",
                "montant_ht_xaf": "1000",
                "montant_ttc_xaf": "1180",
            },
        ],
        "employees": [
            {"id_externe": "E1", "nom_complet": "A", "salaire_base_xaf": "300000"},
        ],
        "periode": "2026-01",
    }
    r = client.post("/v1/bi/kpis", json=payload)
    assert r.status_code == 200
    codes = {k["code"]: k["valeur"] for k in r.json()["kpis"]}
    assert codes["ca_ht"] == "1000"
    assert codes["effectif"] == "1"


def test_finance_analyze(client) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "transactions": [
            {
                "id_externe": "T1",
                "date_operation": "2026-01-10",
                "libelle": "Loyer",
                "montant_xaf": "200000",
                "sens": "debit",
            },
            {
                "id_externe": "T2",
                "date_operation": "2026-01-10",
                "libelle": "Loyer",
                "montant_xaf": "200000",
                "sens": "debit",
            },
            {
                "id_externe": "T3",
                "date_operation": "2026-01-11",
                "libelle": "Gros achat",
                "montant_xaf": "1500000",
                "sens": "debit",
            },
        ],
        "invoices": [],
        "seuil_depassement_xaf": "1000000",
    }
    r = client.post("/v1/erp/finance/analyze", json=payload)
    assert r.status_code == 200
    types = {f["type"] for f in r.json()["findings"]}
    assert "doublon" in types
    assert "depassement" in types
