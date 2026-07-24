"""Parcours end-to-end — Multi-devise.

Chaîne : gouvernance d'un taux (saisie → validation) → saisie d'une facture en
devise étrangère normalisée en XAF au taux validé → le cockpit BI agrège en XAF
normalisé (cohérence des KPIs). Prouve l'abstention si le taux n'est pas validé.
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parcours_md.db")
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


def _kpi(cockpit: dict, code: str) -> Decimal:  # type: ignore[type-arg]
    return Decimal(next(k["valeur"] for k in cockpit["kpis"] if k["code"] == code))


async def test_parcours_devise_gouvernee_vers_kpis(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        base = {
            "numero": "V-USD-1",
            "tiers": "Export Corp",
            "date_emission": "2026-07-01",
            "sens": "vente",
            "devise": "USD",
            "montant_ht_devise": "1000",
            "montant_ttc_devise": "1000",
        }

        # 1. USD non validé → la facture est refusée (abstention, aucun taux fabriqué).
        r = await ac.post("/v1/erp/invoices", json=base)
        assert r.status_code == 409
        assert r.json()["detail"] == "taux_non_valide:USD"

        # 2. Gouvernance : saisir puis valider le taux USD.
        await ac.put("/v1/erp/fx/rates/USD", json={"taux_vers_xaf": "600", "source": "BEAC"})
        await ac.post(
            "/v1/erp/fx/rates/USD/validate", json={"validated": True, "validated_by": "DAF"}
        )

        # 3. Facture EUR (parité fixe, validée d'origine) → normalisée en XAF.
        eur = (
            await ac.post(
                "/v1/erp/invoices",
                json={
                    "numero": "V-EUR-1",
                    "tiers": "Client UE",
                    "date_emission": "2026-07-02",
                    "sens": "vente",
                    "devise": "EUR",
                    "montant_ht_devise": "1000",
                    "montant_ttc_devise": "1180",
                },
            )
        ).json()
        assert Decimal(eur["montant_ht_xaf"]) == Decimal("655957")  # 1000 × 655,957

        # 4. La facture USD passe désormais (taux validé) : 1000 × 600.
        usd = (await ac.post("/v1/erp/invoices", json=base)).json()
        assert Decimal(usd["montant_ht_xaf"]) == Decimal("600000")

        # 5. Le cockpit agrège en XAF normalisé : CA = 655 957 + 600 000.
        ck = (await ac.get("/v1/bi/cockpit")).json()
        assert _kpi(ck, "ca_ht") == Decimal("1255957")
