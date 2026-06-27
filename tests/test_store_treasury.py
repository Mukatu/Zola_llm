"""Tests TRESO-1 — trésorerie : position (moteur) + CRUD comptes/flux + position (endpoint)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.treasury import (
    CompteTresorerie,
    FluxPrevu,
    FluxRapprochable,
    FluxTresorerie,
    LigneReleve,
    indicateurs_tresorerie,
    position_tresorerie,
    previsionnel_tresorerie,
    rapprocher,
)
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/treso.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
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


# ----------------------------------------------------------------- moteur (pur)


def test_position_realisee_et_projetee() -> None:
    comptes = [
        CompteTresorerie(code="BNK", libelle="BGFI", solde_initial_xaf=Decimal("1000000")),
        CompteTresorerie(
            code="CAI", libelle="Caisse", type="caisse", solde_initial_xaf=Decimal("50000")
        ),
    ]
    flux = [
        FluxTresorerie(
            compte_code="BNK", sens="encaissement", montant_xaf="500000", statut="realise"
        ),
        FluxTresorerie(
            compte_code="BNK", sens="decaissement", montant_xaf="200000", statut="realise"
        ),
        FluxTresorerie(
            compte_code="BNK", sens="decaissement", montant_xaf="300000", statut="prevu"
        ),
        FluxTresorerie(
            compte_code="CAI", sens="decaissement", montant_xaf="10000", statut="realise"
        ),
    ]
    p = position_tresorerie(comptes, flux)
    bnk = next(c for c in p.par_compte if c.code == "BNK")
    assert bnk.solde_realise_xaf == Decimal("1300000.00")  # 1M + 500k - 200k
    assert bnk.solde_projete_xaf == Decimal("1000000.00")  # 1.3M - 300k prévu
    # total réalisé consolidé : 1.3M + (50k - 10k) = 1.34M
    assert p.total_realise_xaf == Decimal("1340000.00")
    assert p.par_devise["XAF"] == "1340000.00"


def test_rapprochement_bancaire() -> None:
    flux = [
        FluxRapprochable(
            id="F1", sens="encaissement", montant_xaf="500000", date_operation=date(2026, 6, 15)
        ),
        FluxRapprochable(
            id="F2", sens="decaissement", montant_xaf="200000", date_operation=date(2026, 6, 16)
        ),
        FluxRapprochable(
            id="F3", sens="decaissement", montant_xaf="999999", date_operation=date(2026, 6, 1)
        ),
    ]
    releve = [
        LigneReleve(date=date(2026, 6, 15), montant_xaf="500000", sens="encaissement"),
        LigneReleve(date=date(2026, 6, 18), montant_xaf="200000", sens="decaissement"),  # +2 j ok
        LigneReleve(
            date=date(2026, 6, 18), montant_xaf="123456", sens="encaissement"
        ),  # sans correspondance
    ]
    res = rapprocher(flux, releve, fenetre_jours=5)
    assert len(res.rapprochements) == 2
    assert res.flux_non_rapproches == ["F3"]
    assert res.releve_non_rapproche == [2]
    assert str(res.taux_rapprochement_pct) == "66.7"


def test_previsionnel_et_decouvert() -> None:
    flux = [
        FluxPrevu(
            sens="decaissement", montant_xaf="2000000", date=date.today() + timedelta(days=3)
        ),
        FluxPrevu(
            sens="encaissement", montant_xaf="500000", date=date.today() + timedelta(days=10)
        ),
    ]
    prev = previsionnel_tresorerie(
        Decimal("1000000"), flux, as_of=date.today(), horizon_jours=30, pas_jours=7
    )
    # S1 (j0-6) : -2M → solde 1M-2M = -1M → découvert ; S2 (j7-13) : +0.5M → -0.5M
    assert prev.decouvert_periode == "S1"
    assert prev.position_finale_xaf == Decimal("-500000.00")


def test_indicateurs_dso_dpo_bfr_runway() -> None:
    ind = indicateurs_tresorerie(
        encours_clients=Decimal("3000000"),
        encours_fournisseurs=Decimal("1500000"),
        ca=Decimal("36500000"),
        achats=Decimal("18250000"),
        valeur_stock=Decimal("1000000"),
        position_actuelle=Decimal("2000000"),
        net_mensuel_prevu=Decimal("-500000"),
    )
    assert ind.dso_jours == 30  # 3M / 36.5M * 365
    assert ind.dpo_jours == 30  # 1.5M / 18.25M * 365
    assert ind.bfr_xaf == Decimal("2500000.00")  # 3M + 1M - 1.5M
    assert ind.runway_mois == Decimal("4.0")  # 2M / 0.5M


# ----------------------------------------------------------------- endpoints


async def test_treasury_crud_and_position(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/bank-accounts",
            json={
                "code": "BNK",
                "libelle": "BGFI Bank",
                "banque": "BGFI",
                "solde_initial_xaf": "1000000",
            },
        )
        assert r.status_code == 201, r.text
        assert len((await ac.get("/v1/erp/bank-accounts")).json()["accounts"]) == 1

        for sens, montant, statut in [
            ("encaissement", "500000", "realise"),
            ("decaissement", "200000", "realise"),
            ("decaissement", "300000", "prevu"),
        ]:
            await ac.post(
                "/v1/erp/cash-flows",
                json={
                    "reference": f"F-{sens}-{statut}",
                    "compte_code": "BNK",
                    "sens": sens,
                    "montant_xaf": montant,
                    "date_operation": "2026-06-15",
                    "statut": statut,
                },
            )
        assert len((await ac.get("/v1/erp/cash-flows")).json()["flows"]) == 3
        # filtre par statut
        assert len((await ac.get("/v1/erp/cash-flows?statut=prevu")).json()["flows"]) == 1

        pos = (await ac.get("/v1/erp/treasury/position")).json()["position"]
        assert pos["nb_comptes"] == 1
        cpt = pos["par_compte"][0]
        assert cpt["solde_realise_xaf"] == "1300000.00"
        assert cpt["solde_projete_xaf"] == "1000000.00"
        assert pos["total_realise_xaf"] == "1300000.00"


async def test_decaissement_double_validation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/bank-accounts",
            json={"code": "BNK", "libelle": "BGFI", "solde_initial_xaf": "0"},
        )
        flow = (
            await ac.post(
                "/v1/erp/cash-flows",
                json={
                    "reference": "DEC-XL",
                    "compte_code": "BNK",
                    "sens": "decaissement",
                    "montant_xaf": "5000000",  # > seuil
                    "date_operation": "2026-06-15",
                    "statut": "prevu",
                },
            )
        ).json()
        # N1 : au-dessus du seuil → pas exécuté
        r1 = await ac.post(f"/v1/erp/cash-flows/{flow['id']}/approve")
        assert r1.json()["execute"] is False and r1.json()["requiert_n2"] is True
        assert r1.json()["flow"]["niveau_validation"] == "n1"
        # N2 : exécuté → réalisé
        r2 = await ac.post(f"/v1/erp/cash-flows/{flow['id']}/approve")
        assert r2.json()["execute"] is True
        assert r2.json()["flow"]["statut"] == "realise"
        # déjà exécuté → 409
        assert (await ac.post(f"/v1/erp/cash-flows/{flow['id']}/approve")).status_code == 409


async def test_treasury_reconcile_endpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/bank-accounts",
            json={"code": "BNK", "libelle": "BGFI", "solde_initial_xaf": "0"},
        )
        await ac.post(
            "/v1/erp/cash-flows",
            json={
                "reference": "ENC-1",
                "compte_code": "BNK",
                "sens": "encaissement",
                "montant_xaf": "500000",
                "date_operation": "2026-06-15",
                "statut": "realise",
            },
        )
        body = (
            await ac.post(
                "/v1/erp/treasury/reconcile",
                json={
                    "releve": [
                        {"date": "2026-06-16", "montant_xaf": "500000", "sens": "encaissement"}
                    ]
                },
            )
        ).json()
        assert len(body["rapprochements"]) == 1
        assert body["taux_rapprochement_pct"] == "100.0"
        # le flux est marqué rapproché → un 2e rapprochement ne le réapparie pas
        again = (
            await ac.post(
                "/v1/erp/treasury/reconcile",
                json={
                    "releve": [
                        {"date": "2026-06-16", "montant_xaf": "500000", "sens": "encaissement"}
                    ]
                },
            )
        ).json()
        assert len(again["rapprochements"]) == 0


async def test_treasury_pilotage_and_export(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        await ac.post(
            "/v1/erp/bank-accounts",
            json={"code": "BNK", "libelle": "BGFI", "solde_initial_xaf": "1000000"},
        )
        # un décaissement prévu dans 5 jours
        d5 = (date.today() + timedelta(days=5)).isoformat()
        await ac.post(
            "/v1/erp/cash-flows",
            json={
                "reference": "DEC-PREV",
                "compte_code": "BNK",
                "sens": "decaissement",
                "montant_xaf": "300000",
                "date_operation": d5,
                "date_prevue": d5,
                "statut": "prevu",
            },
        )
        # une facture client impayée (encours clients → DSO)
        await ac.post(
            "/v1/erp/invoices",
            json={
                "numero": "FV-1",
                "tiers": "ACME",
                "date_emission": "2026-06-01",
                "montant_ttc_xaf": "2000000",
            },
        )

        body = (await ac.get("/v1/erp/treasury/pilotage?horizon_jours=30")).json()
        prev = body["previsionnel"]
        assert prev["position_initiale_xaf"] == "1000000.00"
        assert len(prev["periodes"]) >= 1
        assert body["indicateurs"]["encours_clients_xaf"] == "2000000.00"

        r = await ac.get("/v1/erp/treasury/pilotage/export?horizon_jours=30")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers["content-type"]
