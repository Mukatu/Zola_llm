"""Parcours end-to-end — Comptabilité → BI.

Valide la **chaîne complète** (pas des endpoints isolés) : on écrit des factures
dans le registre, on vérifie que le cockpit BI les reflète (CA, encours, DSO),
puis on encaisse et on vérifie que les KPIs se mettent à jour de façon cohérente.
Déterministe, sans LLM. Le bypass d'auth de conftest s'applique.
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
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/parcours_compta.db")
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


async def test_parcours_facturation_vers_cockpit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # 1. Registre vierge → cockpit à zéro.
        ck0 = (await ac.get("/v1/bi/cockpit")).json()
        assert _kpi(ck0, "ca_ht") == 0
        assert _kpi(ck0, "encours_clients") == 0

        # 2. Deux factures de vente (HT 1 000 000 / TTC 1 180 000 chacune).
        f1 = (
            await ac.post(
                "/v1/erp/invoices",
                json={
                    "numero": "V-001",
                    "tiers": "Client A",
                    "date_emission": "2026-07-01",
                    "sens": "vente",
                    "montant_ht_xaf": "1000000",
                    "montant_ttc_xaf": "1180000",
                },
            )
        ).json()
        await ac.post(
            "/v1/erp/invoices",
            json={
                "numero": "V-002",
                "tiers": "Client B",
                "date_emission": "2026-07-02",
                "sens": "vente",
                "montant_ht_xaf": "1000000",
                "montant_ttc_xaf": "1180000",
            },
        )

        # 3. Le cockpit reflète le CA et l'encours (les 2 factures impayées).
        ck1 = (await ac.get("/v1/bi/cockpit")).json()
        assert _kpi(ck1, "ca_ht") == Decimal("2000000")
        assert _kpi(ck1, "encours_clients") == Decimal("2360000")
        dso_avant = _kpi(ck1, "dso")
        assert dso_avant > 0  # encours non nul → DSO non nul

        # 4. Une facture d'achat → la marge brute chute.
        await ac.post(
            "/v1/erp/invoices",
            json={
                "numero": "A-001",
                "tiers": "Fournisseur X",
                "date_emission": "2026-07-03",
                "sens": "achat",
                "montant_ht_xaf": "500000",
                "montant_ttc_xaf": "590000",
            },
        )
        ck2 = (await ac.get("/v1/bi/cockpit")).json()
        assert _kpi(ck2, "marge_brute") == Decimal("1500000")  # 2M CA − 0,5M achats
        assert _kpi(ck2, "encours_fournisseurs") == Decimal("590000")

        # 5. Encaisser V-001 → l'encours clients baisse d'une facture.
        pay = await ac.post(f"/v1/erp/invoices/{f1['id']}/pay")
        assert pay.status_code == 200
        ck3 = (await ac.get("/v1/bi/cockpit")).json()
        assert _kpi(ck3, "encours_clients") == Decimal("1180000")  # une seule reste impayée
        assert _kpi(ck3, "ca_ht") == Decimal("2000000")  # le CA ne bouge pas
        # DSO diminue mécaniquement (moins d'encours pour le même CA).
        assert _kpi(ck3, "dso") < dso_avant
