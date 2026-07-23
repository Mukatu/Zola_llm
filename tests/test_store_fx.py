"""Change / multi-devise (MULTIDEV-1) — moteur de conversion + endpoints gouvernés.

Vérifie la parité fixe EUR (655,957), l'abstention sur taux non validé, et le
cycle de gouvernance (saisie → non validé → validation → conversion autorisée).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.agents.erp.fx import (
    FxRate,
    FxRateNotValidated,
    convertir,
    effective_rates,
    load_fx_seed,
)
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


# ---------------------------------------------------------------- moteur (pur)


def _rates() -> dict[str, FxRate]:
    return effective_rates(load_fx_seed("cg"), {})


def test_parite_eur_fixe() -> None:
    """1 EUR = 655,957 XAF (parité BEAC), validée d'origine."""
    rates = _rates()
    assert rates["EUR"].validated is True
    assert convertir(Decimal("100"), "EUR", "XAF", rates) == Decimal("65595.70")
    # Aller-retour cohérent.
    assert convertir(Decimal("65595.70"), "XAF", "EUR", rates) == Decimal("100.00")


def test_xof_parite_identique() -> None:
    rates = _rates()
    assert convertir(Decimal("1000"), "XOF", "XAF", rates) == Decimal("1000.00")
    assert convertir(Decimal("500"), "EUR", "XOF", rates) == Decimal("327978.50")


def test_identite_et_casse() -> None:
    rates = _rates()
    assert convertir(Decimal("42"), "xaf", "XAF", rates) == Decimal("42.00")
    assert convertir(Decimal("1"), "eur", "xaf", rates) == Decimal("655.96")


def test_abstention_taux_non_valide() -> None:
    """USD livré non validé (aucun taux fabriqué) → conversion refusée."""
    rates = _rates()
    assert rates["USD"].validated is False
    with pytest.raises(FxRateNotValidated) as exc:
        convertir(Decimal("100"), "USD", "XAF", rates)
    assert exc.value.devise == "USD"


# ----------------------------------------------------------------- endpoints


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/fx.db")
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


async def test_fx_rates_seed_defaults(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        data = (await ac.get("/v1/erp/fx/rates")).json()
        assert data["base"] == "XAF"
        by = {r["devise"]: r for r in data["rates"]}
        assert data["rates"][0]["devise"] == "XAF"  # base en tête
        assert by["EUR"]["validated"] is True
        assert by["EUR"]["taux_vers_xaf"] == "655.957"
        assert by["EUR"]["source_donnees"] == "defaut"
        assert by["USD"]["validated"] is False
        assert by["USD"]["taux_vers_xaf"] is None


async def test_fx_governance_cycle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        # Convertir USD non validé → 409 (abstention).
        r = await ac.get("/v1/erp/fx/convert", params={"montant": "100", "de": "USD", "vers": "XAF"})
        assert r.status_code == 409
        assert r.json()["detail"] == "taux_non_valide:USD"

        # Saisir un taux USD → override non validé.
        edited = (
            await ac.put("/v1/erp/fx/rates/USD", json={"taux_vers_xaf": "600", "source": "BEAC test"})
        ).json()
        usd = next(x for x in edited["rates"] if x["devise"] == "USD")
        assert usd["source_donnees"] == "tenant"
        assert usd["validated"] is False
        assert usd["taux_vers_xaf"] == "600.000000"

        # Toujours refusé tant que non validé.
        r = await ac.get("/v1/erp/fx/convert", params={"montant": "100", "de": "USD", "vers": "XAF"})
        assert r.status_code == 409

        # Valider → conversion autorisée.
        await ac.post("/v1/erp/fx/rates/USD/validate", json={"validated": True, "validated_by": "DAF"})
        conv = (
            await ac.get("/v1/erp/fx/convert", params={"montant": "100", "de": "USD", "vers": "XAF"})
        ).json()
        assert conv["resultat"] == "60000.00"

        # Éditer à nouveau → le verrou retombe (re-validation requise).
        await ac.put("/v1/erp/fx/rates/USD", json={"taux_vers_xaf": "610", "source": "maj"})
        r = await ac.get("/v1/erp/fx/convert", params={"montant": "100", "de": "USD", "vers": "XAF"})
        assert r.status_code == 409


async def test_fx_base_non_editable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.put("/v1/erp/fx/rates/XAF", json={"taux_vers_xaf": "2", "source": "x"})
        assert r.status_code == 422
        assert r.json()["detail"] == "devise_base_non_editable"


async def test_fx_validate_without_taux_404(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post("/v1/erp/fx/rates/GBP/validate", json={"validated": True})
        assert r.status_code == 404
        assert r.json()["detail"] == "aucun_taux_tenant_a_valider"
