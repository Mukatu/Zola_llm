"""Tests endpoint Cortex GET /v1/cortex/billing (cockpit usage & facturation).

Couvre :
- Agrégation mensuelle de `core.usage_daily` par tenant, résolution nom + tier
  (licence non révoquée la plus récente), application du barème configuré
- GET /v1/cortex/billing/pricing (barème courant)
- Période invalide → 422
- Routes 404 en profil box (montées uniquement en profil cortex)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.billing.ledger import record_usage_durable
from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import LicenseGrant, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache

_BUSINESS_PRICING_JSON = (
    '{"business": {"monthly_base": 150000, "included_requests": 50000, '
    '"overage_per_1k": 500, "currency": "XAF"}}'
)

# Mois distinctif du passé, dédié à ces tests, pour ne jamais se mélanger avec
# de l'usage réel du mois courant sur cette table globale.
_PERIOD = "2019-03"
_DAY_1 = date(2019, 3, 5)
_DAY_2 = date(2019, 3, 20)


# ----------------------------------------------------------------------------
# Fixtures profil + barème + reset DB engine
# ----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _force_cortex_profile():
    prev = os.environ.get("ZOLAOS_PROFILE", "box")
    os.environ["ZOLAOS_PROFILE"] = "cortex"
    get_settings.cache_clear()
    yield
    os.environ["ZOLAOS_PROFILE"] = prev
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    reset_engine_cache()
    yield
    reset_engine_cache()


@pytest.fixture()
def _business_pricing():
    prev = os.environ.get("BILLING_PRICING_JSON")
    os.environ["BILLING_PRICING_JSON"] = _BUSINESS_PRICING_JSON
    get_settings.cache_clear()
    yield
    if prev is None:
        os.environ.pop("BILLING_PRICING_JSON", None)
    else:
        os.environ["BILLING_PRICING_JSON"] = prev
    get_settings.cache_clear()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def _make_admin(session) -> User:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@polaris.cg",
        display_name="Admin Test",
        password_hash=hash_password("admin-password-123!"),
        country="cg",
        role="admin",
    )
    session.add(admin)
    await session.flush()
    return admin


def _make_client_tenant() -> Tenant:
    return Tenant(name=f"client-{uuid.uuid4().hex[:6]}", tenant_type="client", country="cg")


def _admin_jwt(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=str(user_id),
        settings=get_settings(),
        extra_claims={"scopes": ["cortex", "admin:users"]},
    )


def _row_for(rows: list[dict], tenant_id: uuid.UUID) -> dict:
    return next(r for r in rows if r["tenant_id"] == str(tenant_id))


async def _cleanup_usage(session, tenant_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.usage_daily WHERE tenant_id = :t"), {"t": tenant_id}
    )
    await session.commit()


async def _cleanup(session, tenant_ids: list[uuid.UUID], user_ids: list[uuid.UUID]) -> None:
    for tid in tenant_ids:
        await session.execute(
            text("DELETE FROM core.license_grants WHERE tenant_id = :t"), {"t": str(tid)}
        )
    for uid in user_ids:
        await session.execute(text("DELETE FROM core.users WHERE id = :id"), {"id": str(uid)})
    for tid in tenant_ids:
        await session.execute(text("DELETE FROM core.tenants WHERE id = :id"), {"id": str(tid)})
    await session.commit()


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_billing_aggregates_and_prices(_business_pricing) -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    now = datetime.now(UTC)

    async with factory() as s:
        admin = await _make_admin(s)
        client_tenant = _make_client_tenant()
        s.add(client_tenant)
        await s.flush()

        grant = LicenseGrant(
            tenant_id=client_tenant.id,
            license_id=f"lic-{uuid.uuid4().hex}",
            tier="business",
            modules=[],
            token="a.b.c",
            issued_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=60),
            created_at=now,
        )
        s.add(grant)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    tenant_id_str = str(tenant_id)
    try:
        async with factory() as s:
            # Réparti sur 2 jours du mois distinctif, total 62000 requêtes.
            await record_usage_durable(
                s, tenant_id=tenant_id_str, day=_DAY_1, requests=50_000, tokens=100
            )
            await record_usage_durable(
                s, tenant_id=tenant_id_str, day=_DAY_2, requests=12_000, tokens=50
            )
            await s.commit()

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(
                "/v1/cortex/billing",
                params={"period": _PERIOD},
                headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["period"] == _PERIOD

        row = _row_for(body["rows"], tenant_id)
        assert row["name"] is not None
        assert row["tier"] == "business"
        assert row["requests"] == 62_000
        assert row["tokens"] == 150
        assert row["cost"]["total"] == 156_000
        assert row["cost"]["overage_requests"] == 12_000

        assert body["total_requests"] == 62_000
        assert body["total_tokens"] == 150
        assert body["total_cost"] == 156_000
    finally:
        async with factory() as s:
            await _cleanup_usage(s, tenant_id_str)
        async with factory() as s:
            await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_billing_pricing_endpoint(_business_pricing) -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin = await _make_admin(s)
        await s.commit()
        admin_id = admin.id

    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(
                "/v1/cortex/billing/pricing",
                headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "business" in body
        price = body["business"]
        assert price["monthly_base"] == 150000
        assert price["included_requests"] == 50000
        assert price["overage_per_1k"] == 500
        assert price["currency"] == "XAF"
    finally:
        async with factory() as s:
            await _cleanup(s, [], [admin_id])


@pytest.mark.asyncio
async def test_billing_invalid_period() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin = await _make_admin(s)
        await s.commit()
        admin_id = admin.id

    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(
                "/v1/cortex/billing",
                params={"period": "pas-une-date"},
                headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            )
        assert r.status_code == 422, r.text
    finally:
        async with factory() as s:
            await _cleanup(s, [], [admin_id])


def test_billing_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/billing n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/billing") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/billing") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
