"""MULTIDEV-3 — normalisation XAF à l'écriture pour comptes / flux / projets.

Le XAF reste la valeur canonique ; l'original en devise et le taux sont conservés.
Conversion au taux **validé** uniquement (409 sinon). La saisie XAF est inchangée.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/md3.db")
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


async def test_compte_eur_normalise(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/erp/bank-accounts",
                json={
                    "code": "EUR1",
                    "libelle": "Compte EUR",
                    "devise": "EUR",
                    "solde_initial_devise": "1000",
                },
            )
        ).json()
        # 1000 EUR × 655,957 = 655 957 XAF
        assert Decimal(rec["solde_initial_xaf"]) == Decimal("655957")
        assert Decimal(rec["solde_initial_devise"]) == Decimal("1000")
        assert Decimal(rec["taux_applique"]) == Decimal("655.957")


async def test_compte_xaf_inchange(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/erp/bank-accounts",
                json={"code": "X1", "libelle": "Caisse", "solde_initial_xaf": "5000"},
            )
        ).json()
        assert Decimal(rec["solde_initial_xaf"]) == Decimal("5000")
        assert rec["solde_initial_devise"] is None
        assert rec["taux_applique"] is None


async def test_compte_devise_sans_montant_422(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/bank-accounts", json={"code": "E", "libelle": "x", "devise": "EUR"}
        )
        assert r.status_code == 422
        assert r.json()["detail"] == "montant_devise_requis"


async def test_flux_usd_refuse_puis_normalise(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        base = {
            "reference": "F1",
            "compte_code": "BQ1",
            "sens": "encaissement",
            "date_operation": "2026-07-24",
            "devise": "USD",
            "montant_devise": "100",
        }
        # USD non validé → 409.
        r = await ac.post("/v1/erp/cash-flows", json=base)
        assert r.status_code == 409
        assert r.json()["detail"] == "taux_non_valide:USD"

        # Gouverner USD puis normaliser.
        await ac.put("/v1/erp/fx/rates/USD", json={"taux_vers_xaf": "600", "source": "t"})
        await ac.post(
            "/v1/erp/fx/rates/USD/validate", json={"validated": True, "validated_by": "DAF"}
        )
        rec = (await ac.post("/v1/erp/cash-flows", json=base)).json()
        assert Decimal(rec["montant_xaf"]) == Decimal("60000")
        assert rec["devise"] == "USD"
        assert Decimal(rec["taux_applique"]) == Decimal("600")


async def test_projet_eur_normalise(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/erp/projects",
                json={
                    "intitule": "Eau",
                    "bailleur": "UE",
                    "devise": "EUR",
                    "budget_total_devise": "50000",
                },
            )
        ).json()
        # 50000 EUR × 655,957 = 32 797 850 XAF
        assert Decimal(rec["budget_total"]) == Decimal("32797850")
        assert Decimal(rec["budget_total_devise"]) == Decimal("50000")
        assert Decimal(rec["taux_applique"]) == Decimal("655.957")
