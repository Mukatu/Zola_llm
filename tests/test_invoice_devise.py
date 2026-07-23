"""MULTIDEV-2 — saisie de factures en devise, normalisation XAF à l'écriture.

Le XAF reste la valeur canonique (`montant_*_xaf`) ; l'original en devise et le
taux appliqué sont conservés pour la traçabilité. Conversion au **taux validé**
uniquement (abstention sinon). La saisie en XAF reste inchangée (rétrocompat).
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/inv_devise.db")
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


_BASE = {"numero": "F-1", "tiers": "ACME", "date_emission": "2026-07-23", "sens": "vente"}


async def test_facture_xaf_inchangee(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Rétrocompat : une facture XAF est stockée telle quelle, sans champ devise."""
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/erp/invoices",
                json={**_BASE, "montant_ht_xaf": "1000", "montant_ttc_xaf": "1180"},
            )
        ).json()
        assert rec["devise"] == "XAF"
        assert Decimal(rec["montant_ttc_xaf"]) == Decimal("1180")
        assert rec["montant_ttc_devise"] is None
        assert rec["taux_applique"] is None


async def test_facture_eur_normalisee(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """EUR (parité fixe validée) : montant TTC converti en XAF + original conservé."""
    async with _client(tmp_path) as ac:
        rec = (
            await ac.post(
                "/v1/erp/invoices",
                json={
                    **_BASE,
                    "devise": "EUR",
                    "montant_ht_devise": "100",
                    "montant_ttc_devise": "120",
                },
            )
        ).json()
        assert rec["devise"] == "EUR"
        # 120 EUR × 655,957 = 78714,84 XAF ; 100 EUR × 655,957 = 65595,70
        assert Decimal(rec["montant_ttc_xaf"]) == Decimal("78714.84")
        assert Decimal(rec["montant_ht_xaf"]) == Decimal("65595.70")
        assert Decimal(rec["montant_tva_xaf"]) == Decimal("13119.14")
        assert Decimal(rec["montant_ttc_devise"]) == Decimal("120")
        assert Decimal(rec["taux_applique"]) == Decimal("655.957")


async def test_facture_devise_sans_montant_422(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post("/v1/erp/invoices", json={**_BASE, "devise": "EUR"})
        assert r.status_code == 422
        assert r.json()["detail"] == "montant_devise_requis"


async def test_facture_devise_non_validee_409(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """USD non validé → la facture est refusée (pas de taux fabriqué)."""
    async with _client(tmp_path) as ac:
        r = await ac.post(
            "/v1/erp/invoices",
            json={**_BASE, "devise": "USD", "montant_ttc_devise": "100"},
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "taux_non_valide:USD"


async def test_facture_usd_apres_gouvernance(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Une fois le taux USD saisi et validé, la facture USD se normalise."""
    async with _client(tmp_path) as ac:
        await ac.put("/v1/erp/fx/rates/USD", json={"taux_vers_xaf": "600", "source": "test"})
        await ac.post("/v1/erp/fx/rates/USD/validate", json={"validated": True, "validated_by": "DAF"})
        rec = (
            await ac.post(
                "/v1/erp/invoices",
                json={**_BASE, "devise": "USD", "montant_ttc_devise": "100"},
            )
        ).json()
        assert Decimal(rec["montant_ttc_xaf"]) == Decimal("60000")
        assert Decimal(rec["taux_applique"]) == Decimal("600")
        # L'agrégation lit montant_ttc_xaf (normalisé) — cohérence des KPIs.
