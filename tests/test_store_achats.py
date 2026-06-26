"""Tests P2c — Achats persisté : fournisseurs (scoring/conformité), BC, réception→facture.

SQLite (override de get_session). Réutilise le moteur Achats déterministe sur le store.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/achats.db")
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


async def test_supplier_crud_and_scores(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/suppliers",
            json={
                "id_externe": "F1",
                "nom": "Fourni Plus",
                "note_qualite": "4.5",
                "delai_moyen_jours": 10,
                "documents_conformite": ["rccm", "niu", "attestation_fiscale"],
            },
        )
        assert r.status_code == 201, r.text
        await ac.post(
            "/v1/erp/suppliers",
            json={
                "id_externe": "F2",
                "nom": "Low Cost",
                "note_qualite": "1.0",
                "delai_moyen_jours": 40,
                "documents_conformite": ["rccm"],
            },
        )
        assert len((await ac.get("/v1/erp/suppliers")).json()["suppliers"]) == 2

        scores = (await ac.get("/v1/erp/suppliers/scores")).json()["scores"]
        # tri décroissant : le fournisseur conforme et bien noté arrive premier
        assert scores[0]["nom"] == "Fourni Plus"
        assert scores[0]["grade"] == "A"
        # F2 incomplet : pièces de conformité manquantes signalées
        f2 = next(s for s in scores if s["nom"] == "Low Cost")
        assert set(f2["conformite_manquante"]) == {"niu", "attestation_fiscale"}


async def test_purchase_order_compare(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        for i, (montant, delai) in enumerate([("5000000", 20), ("4200000", 25), ("4500000", 10)]):
            await ac.post(
                "/v1/erp/purchase-orders",
                json={
                    "id_externe": f"BC{i}",
                    "numero": f"BC-00{i}",
                    "fournisseur": f"Four{i}",
                    "objet": "Serveurs",
                    "date_emission": "2026-06-01",
                    "montant_ht_xaf": montant,
                    "montant_ttc_xaf": montant,
                    "delai_livraison_jours": delai,
                },
            )
        classement = (await ac.get("/v1/erp/purchase-orders/compare?objet=Serveurs")).json()[
            "classement"
        ]
        assert len(classement) == 3
        assert classement[0]["rang"] == 1
        # chaque offre a un rang unique 1..3
        assert {c["rang"] for c in classement} == {1, 2, 3}


async def test_receipt_creates_purchase_invoice(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        po_id = (
            await ac.post(
                "/v1/erp/purchase-orders",
                json={
                    "id_externe": "BC1",
                    "numero": "BC-001",
                    "fournisseur": "Fourni Plus",
                    "objet": "Serveurs",
                    "date_emission": "2026-06-01",
                    "statut": "confirme",
                    "montant_ht_xaf": "5000000",
                    "montant_ttc_xaf": "5900000",
                },
            )
        ).json()["id"]

        r = await ac.post(f"/v1/erp/purchase-orders/{po_id}/receipt")
        assert r.status_code == 200, r.text
        assert r.json()["purchase_order"]["statut"] == "receptionne"
        # la facture d'achat est dans le registre Compta (clôture continue, côté fournisseur)
        invs = (await ac.get("/v1/erp/invoices?sens=achat")).json()["invoices"]
        assert len(invs) == 1
        assert invs[0]["sens"] == "achat"
        assert invs[0]["tiers"] == "Fourni Plus"
        assert invs[0]["montant_ttc_xaf"] == "5900000.00"

        # double réception → 409
        assert (await ac.post(f"/v1/erp/purchase-orders/{po_id}/receipt")).status_code == 409


async def test_receipt_refused_when_brouillon(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        po_id = (
            await ac.post(
                "/v1/erp/purchase-orders",
                json={
                    "id_externe": "BC2",
                    "numero": "BC-002",
                    "fournisseur": "Low Cost",
                    "date_emission": "2026-06-01",
                    "statut": "brouillon",
                    "montant_ht_xaf": "500000",
                    "montant_ttc_xaf": "590000",
                },
            )
        ).json()["id"]
        assert (await ac.post(f"/v1/erp/purchase-orders/{po_id}/receipt")).status_code == 422
