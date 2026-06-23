"""Tests persistance Factures (CRUD) + clôture continue.

Repository/endpoints testés sur SQLite (override de get_session). Moteur de
réconciliation testé en pur.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.reconciliation import reconcilier
from zolaos.api.main import create_app
from zolaos.connectors.models import BankTransaction, Invoice
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


async def _make_client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/store.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ----------------------------------------------------- moteur (pur)


def _inv(idx: str, ttc: str, d: date, *, payee: bool = False) -> Invoice:
    return Invoice(
        id_externe=idx,
        numero=f"F{idx}",
        sens="vente",
        tiers="ACME",
        date_emission=d,
        montant_ht_xaf=Decimal(ttc),
        montant_ttc_xaf=Decimal(ttc),
        payee=payee,
    )


def _tx(idx: str, montant: str, d: date) -> BankTransaction:
    return BankTransaction(
        id_externe=idx,
        date_operation=d,
        libelle="Encaissement",
        montant_xaf=Decimal(montant),
        sens="credit",
        canal="bank",
    )


def test_reconciliation_cloture_continue() -> None:
    invoices = [_inv("I1", "1180", date(2026, 1, 5)), _inv("I2", "2360", date(2026, 1, 10))]
    txs = [_tx("T1", "1180", date(2026, 1, 7))]  # rapproche I1 (écart 2 j)
    rep = reconcilier(invoices, txs, fenetre_jours=5)
    assert rep.cloture is not None
    assert rep.cloture.lettrees == 1
    assert rep.cloture.en_attente == 1
    assert rep.cloture.taux_lettrage_pct == Decimal("50.0")
    assert rep.cloture.encours_clients_xaf == Decimal("2360")
    assert rep.rapprochements[0].invoice_id == "I1"


# ----------------------------------------------------- CRUD + reconcile (sqlite)


async def test_invoice_crud_and_live_close(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with await _make_client(tmp_path) as ac:
        # create
        r = await ac.post(
            "/v1/erp/invoices",
            json={
                "numero": "F-001",
                "tiers": "Polyclinique X",
                "date_emission": "2026-01-05",
                "montant_ht_xaf": "1000",
                "montant_ttc_xaf": "1180",
            },
        )
        assert r.status_code == 201, r.text
        inv_id = r.json()["id"]

        # list
        r = await ac.get("/v1/erp/invoices")
        assert len(r.json()["invoices"]) == 1

        # reconcile (clôture continue) — encaissement correspondant
        r = await ac.post(
            "/v1/erp/reconcile",
            json={
                "transactions": [
                    {
                        "id_externe": "T1",
                        "date_operation": "2026-01-06",
                        "libelle": "Vir",
                        "montant_xaf": "1180",
                        "sens": "credit",
                    }
                ],
            },
        )
        body = r.json()
        assert body["cloture"]["lettrees"] == 1
        assert body["cloture"]["taux_lettrage_pct"] == "100.0"

        # mark paid → plus d'encours
        r = await ac.post(f"/v1/erp/invoices/{inv_id}/pay")
        assert r.json()["payee"] is True
        r = await ac.post("/v1/erp/reconcile", json={"transactions": []})
        assert r.json()["cloture"]["total_factures"] == 0  # plus de facture non payée

        # delete
        r = await ac.delete(f"/v1/erp/invoices/{inv_id}")
        assert r.status_code == 200
