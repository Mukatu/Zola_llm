"""Tests des moteurs Fintech déterministes — scoring crédit et KYC/AML."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.fintech.kyc import (
    AmlBareme,
    KycProfile,
    Transaction,
    evaluate_aml,
    evaluate_kyc,
)
from zolaos.agents.fintech.scoring import CreditRequest, score_credit
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/fintech.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():  # type: ignore[no-untyped-def]
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


_DOSSIER = {
    "revenu_mensuel_xaf": "800000",
    "charges_mensuelles_xaf": "100000",
    "montant_demande_xaf": "1500000",
    "duree_mois": 24,
    "anciennete_activite_mois": 36,
    "incidents_paiement": 0,
    "epargne_xaf": "400000",
    "garanties_xaf": "1500000",
    "type_emploi": "salarie_public",
}

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


# --- Persistance (FINTECH-3) ------------------------------------------------


async def test_application_crud_et_decision(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post("/v1/fintech/applications", json={"client": "Jean M.", "dossier": _DOSSIER})
        assert r.status_code == 201, r.text
        app_id = r.json()["id"]
        assert r.json()["decision"] == "accorde"
        assert r.json()["statut"] == "evaluee"
        assert r.json()["score"] >= 70
        assert r.json()["numero"].startswith("CR-")
        # Snapshot figé du dossier + résultat.
        assert r.json()["dossier"]["montant_demande_xaf"] == "1500000"
        assert len(r.json()["resultat"]["facteurs"]) == 6

        lst = await ac.get("/v1/fintech/applications")
        assert len(lst.json()["applications"]) == 1

        got = await ac.get(f"/v1/fintech/applications/{app_id}")
        assert got.status_code == 200

        dec = await ac.post(f"/v1/fintech/applications/{app_id}/decision", json={"statut": "accordee", "commentaire": "OK CA"})
        assert dec.status_code == 200
        assert dec.json()["statut"] == "accordee"
        assert dec.json()["commentaire"] == "OK CA"

        bad = await ac.post(f"/v1/fintech/applications/{app_id}/decision", json={"statut": "n_importe_quoi"})
        assert bad.status_code == 422

        d = await ac.delete(f"/v1/fintech/applications/{app_id}")
        assert d.status_code == 200
        assert (await ac.get("/v1/fintech/applications")).json()["applications"] == []


async def test_application_isolation_tenant(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post("/v1/fintech/applications", params={"tenant_id": "A"}, json={"client": "A", "dossier": _DOSSIER})
        assert len((await ac.get("/v1/fintech/applications", params={"tenant_id": "A"})).json()["applications"]) == 1
        assert (await ac.get("/v1/fintech/applications", params={"tenant_id": "B"})).json()["applications"] == []


async def test_kyc_record_persistance_et_decision(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/fintech/kyc-records",
            json={"nom": "ACME", "type_client": "entreprise", "pieces_fournies": ["rccm"]},
        )
        assert r.status_code == 201, r.text
        rec_id = r.json()["id"]
        assert r.json()["complet"] is False
        assert r.json()["statut"] == "a_valider"
        assert set(r.json()["resultat"]["pieces_manquantes"]) == {"niu", "statuts", "piece_dirigeant"}

        dec = await ac.post(f"/v1/fintech/kyc-records/{rec_id}/decision", json={"statut": "refuse"})
        assert dec.status_code == 200
        assert dec.json()["statut"] == "refuse"

        assert len((await ac.get("/v1/fintech/kyc-records")).json()["kyc_records"]) == 1
