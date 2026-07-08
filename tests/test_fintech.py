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
from zolaos.agents.fintech.portfolio import portfolio_stats
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


# --- Pilotage portefeuille (FINTECH-5) --------------------------------------


class _App:  # objet duck-typé pour le moteur d'agrégation
    def __init__(self, statut, montant, score, grade, mensualite) -> None:  # type: ignore[no-untyped-def]
        self.statut = statut
        self.montant_demande_xaf = Decimal(montant)
        self.score = score
        self.grade = grade
        self.mensualite_xaf = Decimal(mensualite)


class _Kyc:
    def __init__(self, statut, niveau_risque, vigilance) -> None:  # type: ignore[no-untyped-def]
        self.statut = statut
        self.niveau_risque = niveau_risque
        self.vigilance = vigilance


def test_portfolio_stats_agregation() -> None:
    from zolaos.agents.fintech.portfolio import portfolio_stats

    apps = [
        _App("decaissee", "1000000", 85, "A", "50000"),
        _App("accordee", "2000000", 72, "B", "95000"),
        _App("refusee", "500000", 30, "E", "0"),
        _App("evaluee", "800000", 60, "C", "40000"),
    ]
    kyc = [_Kyc("a_valider", "eleve", "renforcee"), _Kyc("valide", "faible", "standard")]
    s = portfolio_stats(apps, kyc)
    assert s.nb_dossiers == 4
    assert s.par_statut["decaissee"] == 1 and s.par_statut["refusee"] == 1
    assert s.encours_decaisse_xaf == Decimal("1000000")
    assert s.service_dette_mensuel_xaf == Decimal("50000")
    assert s.montant_accorde_xaf == Decimal("3000000")  # accordee + decaissee
    # décidés = accordee+refusee+decaissee = 3 ; acceptés = 2 → 67 %
    assert s.taux_acceptation_pct == Decimal("67")
    assert s.taux_decaissement_pct == Decimal("50")  # 1 décaissée / 2 accordées
    assert s.repartition_grade["A"] == 1 and s.repartition_grade["B"] == 1
    assert s.nb_kyc == 2 and s.nb_vigilance_renforcee == 1
    assert s.kyc_par_risque["eleve"] == 1
    assert "PAR" in s.note  # limite assumée signalée


async def test_portfolio_endpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 2 dossiers évalués (accorde), on en décaisse un.
        a1 = (await ac.post("/v1/fintech/applications", json={"client": "A", "dossier": _DOSSIER})).json()
        await ac.post("/v1/fintech/applications", json={"client": "B", "dossier": _DOSSIER})
        await ac.post(f"/v1/fintech/applications/{a1['id']}/decision", json={"statut": "accordee"})
        await ac.post(f"/v1/fintech/applications/{a1['id']}/decision", json={"statut": "decaissee"})
        await ac.post("/v1/fintech/kyc-records", json={"nom": "K", "type_client": "particulier", "pieces_fournies": ["piece_identite", "justificatif_domicile"]})

        p = (await ac.get("/v1/fintech/portfolio")).json()
        assert p["nb_dossiers"] == 2
        assert p["par_statut"]["decaissee"] == 1
        assert p["par_statut"]["evaluee"] == 1
        assert p["encours_decaisse_xaf"] == "1500000"
        assert p["nb_kyc"] == 1


# --- Échéancier & PAR (FINTECH-6) -------------------------------------------


def test_build_schedule_amortissement() -> None:
    from datetime import date as _date

    from zolaos.agents.fintech.amortization import build_schedule

    sched = build_schedule(Decimal("1200000"), Decimal("0.18"), 12, _date(2026, 1, 15))
    assert len(sched) == 12
    assert sched[0].numero == 1 and sched[0].date_echeance == _date(2026, 2, 15)
    # le principal cumulé rembourse exactement le capital
    assert sum((e.principal_xaf for e in sched), Decimal("0")) == Decimal("1200000")
    # amortissement : intérêts décroissants
    assert sched[0].interet_xaf > sched[-1].interet_xaf


class _Inst:
    def __init__(self, app_id, montant, paye, statut, date_ech) -> None:  # type: ignore[no-untyped-def]
        self.application_id = app_id
        self.montant_xaf = Decimal(montant)
        self.montant_paye_xaf = Decimal(paye)
        self.statut = statut
        self.date_echeance = date_ech


def test_portfolio_par() -> None:
    as_of = date(2026, 6, 1)
    inst = [
        _Inst("L1", "100000", "0", "a_venir", date(2026, 3, 1)),  # ~92 j de retard
        _Inst("L1", "100000", "0", "a_venir", date(2026, 7, 1)),  # à venir
        _Inst("L2", "100000", "100000", "paye", date(2026, 4, 1)),  # soldée
    ]
    s = portfolio_stats([], [], inst, as_of=as_of)
    assert s.echeancier_disponible is True
    assert s.encours_restant_du_xaf == Decimal("200000")
    assert s.nb_prets_en_retard == 1
    assert s.montant_en_retard_xaf == Decimal("100000")
    assert s.par90_pct == Decimal("100")  # L1 (retard > 90 j) = tout l'encours restant
    assert s.par30_pct == Decimal("100")


async def test_disburse_schedule_pay(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        aid = (await ac.post("/v1/fintech/applications", json={"client": "X", "dossier": _DOSSIER})).json()["id"]
        # décaissement réservé aux dossiers accordés
        assert (await ac.post(f"/v1/fintech/applications/{aid}/disburse", json={})).status_code == 409
        await ac.post(f"/v1/fintech/applications/{aid}/decision", json={"statut": "accordee"})
        d = await ac.post(f"/v1/fintech/applications/{aid}/disburse", json={"date_decaissement": "2026-01-15"})
        assert d.status_code == 200
        assert len(d.json()["echeances"]) == 24
        # dossier passé à décaissé
        assert (await ac.get(f"/v1/fintech/applications/{aid}")).json()["statut"] == "decaissee"

        sched = (await ac.get(f"/v1/fintech/applications/{aid}/schedule")).json()
        assert len(sched["echeances"]) == 24
        first = sched["echeances"][0]["id"]
        p = await ac.post(f"/v1/fintech/installments/{first}/pay", json={})
        assert p.status_code == 200 and p.json()["statut"] == "paye"

        pf = (await ac.get("/v1/fintech/portfolio")).json()
        assert pf["echeancier_disponible"] is True
        assert Decimal(pf["encours_restant_du_xaf"]) > 0


# --- Corpus RAG réglementaire (FINTECH-8) -----------------------------------


def test_rag_fintech_wiring() -> None:
    from zolaos.agents.generic import GenericFintechAgent
    from zolaos.agents.registry import POLE_DEFAULT_AGENTS, default_rag_agent_for
    from zolaos.agents.router import Pole
    from zolaos.db.models import RAG_MODELS

    assert "rag_fintech" in RAG_MODELS
    assert GenericFintechAgent.rag_schema == "rag_fintech"
    assert POLE_DEFAULT_AGENTS[Pole.FINTECH] is GenericFintechAgent
    assert default_rag_agent_for(Pole.FINTECH) is GenericFintechAgent


# --- Cohortes / millésimes (FINTECH-7) --------------------------------------


class _CApp:
    def __init__(self, id_, montant, date_dec) -> None:  # type: ignore[no-untyped-def]
        self.id = id_
        self.statut = "decaissee"
        self.montant_demande_xaf = Decimal(montant)
        self.date_decaissement = date_dec


def test_cohortes() -> None:
    from zolaos.agents.fintech.cohortes import cohortes

    apps = [
        _CApp("L1", "1000000", date(2026, 1, 10)),
        _CApp("L2", "500000", date(2026, 1, 20)),
        _CApp("L3", "800000", date(2026, 2, 5)),
    ]
    inst = [
        _Inst("L1", "100000", "100000", "paye", date(2026, 2, 10)),
        _Inst("L1", "100000", "0", "a_venir", date(2026, 3, 10)),
        _Inst("L3", "80000", "80000", "paye", date(2026, 3, 5)),
    ]
    cos = cohortes(apps, inst, date(2026, 6, 1))
    assert [c.periode for c in cos] == ["2026-01", "2026-02"]
    jan = cos[0]
    assert jan.nb_prets == 2
    assert jan.montant_decaisse_xaf == Decimal("1500000")
    assert jan.montant_du_echu_xaf == Decimal("200000")
    assert jan.montant_rembourse_xaf == Decimal("100000")
    assert jan.encours_restant_xaf == Decimal("100000")
    assert jan.montant_en_retard_xaf == Decimal("100000")
    assert jan.taux_remboursement_pct == Decimal("50")
    assert jan.par30_pct == Decimal("100")
    feb = cos[1]
    assert feb.nb_prets == 1
    assert feb.montant_en_retard_xaf == Decimal("0")
    assert feb.taux_remboursement_pct == Decimal("100")


async def test_cohortes_endpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        aid = (await ac.post("/v1/fintech/applications", json={"client": "C", "dossier": _DOSSIER})).json()["id"]
        await ac.post(f"/v1/fintech/applications/{aid}/decision", json={"statut": "accordee"})
        await ac.post(f"/v1/fintech/applications/{aid}/disburse", json={"date_decaissement": "2026-01-15"})
        cos = (await ac.get("/v1/fintech/cohortes")).json()["cohortes"]
        assert len(cos) == 1
        assert cos[0]["periode"] == "2026-01"
        assert cos[0]["nb_prets"] == 1
