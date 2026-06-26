"""Tests TRESO-1 — trésorerie : position (moteur) + CRUD comptes/flux + position (endpoint)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.treasury import CompteTresorerie, FluxTresorerie, position_tresorerie
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
