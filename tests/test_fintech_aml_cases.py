"""Fintech — registre AML (dossiers de surveillance persistés, FINTECH-10).

L'évaluation déterministe est figée à la création ; le workflow (à examiner →
classé sans suite | déclaré) est piloté par l'humain. Multi-tenant isolé.
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/aml.db")
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


# Une opération au-delà du seuil de déclaration (5 000 000) → alerte.
_TX_ALERTE = [
    {"date": "2026-07-01", "montant_xaf": "6000000", "sens": "entree", "canal": "especes"},
]
_TX_RAS = [
    {"date": "2026-07-02", "montant_xaf": "50000", "sens": "entree", "canal": "virement"},
]


async def test_aml_case_persistance_et_alertes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/fintech/aml-cases",
                json={"client": "SARL Négoce", "reference": "AML-1", "transactions": _TX_ALERTE},
            )
        ).json()
        assert rec["statut"] == "a_examiner"
        assert rec["niveau"] == "alerte"
        assert rec["nb_alertes"] == 1
        assert rec["nb_operations"] == 1
        # L'évaluation figée est dans le snapshot.
        assert any(a["code"] == "seuil_unitaire" for a in rec["resultat"]["alertes"])

        listed = (await ac.get("/v1/fintech/aml-cases")).json()["aml_cases"]
        assert any(c["id"] == rec["id"] for c in listed)


async def test_aml_case_ras(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/fintech/aml-cases",
                json={"client": "Particulier X", "transactions": _TX_RAS},
            )
        ).json()
        assert rec["niveau"] == "info"
        assert rec["nb_alertes"] == 0


async def test_aml_case_workflow_declaration(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/fintech/aml-cases",
                json={"client": "SARL Négoce", "transactions": _TX_ALERTE},
            )
        ).json()
        cid = rec["id"]

        # Déclarer sans référence → 422.
        r = await ac.post(f"/v1/fintech/aml-cases/{cid}/decision", json={"statut": "declaree"})
        assert r.status_code == 422
        assert r.json()["detail"] == "declaration_ref_requise"

        # Statut invalide → 422.
        r = await ac.post(f"/v1/fintech/aml-cases/{cid}/decision", json={"statut": "n_importe_quoi"})
        assert r.status_code == 422

        # Déclaration de soupçon avec référence → OK.
        done = (
            await ac.post(
                f"/v1/fintech/aml-cases/{cid}/decision",
                json={"statut": "declaree", "declaration_ref": "ANIF-2026-014", "commentaire": "SAR"},
            )
        ).json()
        assert done["statut"] == "declaree"
        assert done["declaration_ref"] == "ANIF-2026-014"

        # Suppression + 404 sur seconde.
        assert (await ac.delete(f"/v1/fintech/aml-cases/{cid}")).status_code == 200
        assert (await ac.get(f"/v1/fintech/aml-cases/{cid}")).status_code == 404


async def test_aml_case_isolation_tenant(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/fintech/aml-cases?tenant_id=A",
                json={"client": "Client A", "transactions": _TX_ALERTE},
            )
        ).json()
        # Tenant B ne voit pas le dossier de A.
        b_list = (await ac.get("/v1/fintech/aml-cases?tenant_id=B")).json()["aml_cases"]
        assert all(c["id"] != rec["id"] for c in b_list)
        assert (await ac.get(f"/v1/fintech/aml-cases/{rec['id']}?tenant_id=B")).status_code == 404
