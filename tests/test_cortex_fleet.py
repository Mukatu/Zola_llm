"""Tests endpoint Cortex GET /v1/cortex/fleet (supervision des boxes clientes).

Couvre :
- Agrégation par tenant client (statut de licence, box connectée/provisionnée,
  missions actives) ET le résumé (`summary`) toutes lignes confondues
- Seuil « expire bientôt » piloté par le paramètre `expiring_days`
- Résolution de la licence la plus récente (`created_at`) en cas de renouvellement
- Route 404 en profil box (montée uniquement en profil cortex)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import LicenseGrant, Mission, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.tunnel.channel import REGISTRY


# ----------------------------------------------------------------------------
# Fixtures profil + reset DB engine
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


def _make_client_tenant(*, box_provisioned: bool = False) -> Tenant:
    return Tenant(
        name=f"client-{uuid.uuid4().hex[:6]}",
        tenant_type="client",
        country="cg",
        box_credential_prefix="abcd1234" if box_provisioned else None,
    )


def _admin_jwt(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=str(user_id),
        settings=get_settings(),
        extra_claims={"scopes": ["cortex", "admin:users"]},
    )


async def _cleanup(session, tenant_ids: list[uuid.UUID], user_ids: list[uuid.UUID]) -> None:
    for tid in tenant_ids:
        await session.execute(
            text("DELETE FROM core.license_grants WHERE tenant_id = :t"), {"t": str(tid)}
        )
        await session.execute(
            text("DELETE FROM core.missions WHERE client_tenant_id = :t"), {"t": str(tid)}
        )
    for uid in user_ids:
        await session.execute(text("DELETE FROM core.users WHERE id = :id"), {"id": str(uid)})
    for tid in tenant_ids:
        await session.execute(text("DELETE FROM core.tenants WHERE id = :id"), {"id": str(tid)})
    await session.commit()


def _row_for(rows: list[dict], tenant_id: uuid.UUID) -> dict:
    return next(r for r in rows if r["tenant_id"] == str(tenant_id))


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fleet_aggregates_status_and_summary() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    now = datetime.now(UTC)

    async with factory() as s:
        admin = await _make_admin(s)

        active_client = _make_client_tenant(box_provisioned=True)
        expired_client = _make_client_tenant()
        none_client = _make_client_tenant()
        s.add_all([active_client, expired_client, none_client])
        await s.flush()

        active_grant = LicenseGrant(
            tenant_id=active_client.id,
            license_id=f"lic-{uuid.uuid4().hex}",
            tier="business",
            modules=[],
            token="a.b.c",
            issued_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=60),
            created_at=now,
        )
        expired_grant = LicenseGrant(
            tenant_id=expired_client.id,
            license_id=f"lic-{uuid.uuid4().hex}",
            tier="starter",
            modules=[],
            token="a.b.c",
            issued_at=now - timedelta(days=1),
            expires_at=now - timedelta(hours=1),
            created_at=now,
        )
        s.add_all([active_grant, expired_grant])

        # La mission requiert un cabinet distinct du client (contrainte DB).
        cabinet = Tenant(name=f"cab-{uuid.uuid4().hex[:6]}", tenant_type="cabinet", country="cg")
        s.add(cabinet)
        await s.flush()

        mission = Mission(
            cabinet_tenant_id=cabinet.id,
            client_tenant_id=active_client.id,
            offre="conformite_rh",
            consultant_user_id=admin.id,
            expires_at=now + timedelta(hours=1),
            status="active",
            scope_tags=["country:cg"],
        )
        s.add(mission)

        await s.commit()
        admin_id = admin.id
        active_id, expired_id, none_id = active_client.id, expired_client.id, none_client.id
        cabinet_id = cabinet.id

    REGISTRY[str(active_id)] = object()
    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get(
                "/v1/cortex/fleet",
                headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            )
        assert r.status_code == 200, r.text
        body = r.json()

        row_active = _row_for(body["rows"], active_id)
        assert row_active["license_status"] == "active"
        assert row_active["license_tier"] == "business"
        assert row_active["box_provisioned"] is True
        assert row_active["box_connected"] is True
        assert row_active["active_missions"] == 1

        row_expired = _row_for(body["rows"], expired_id)
        assert row_expired["license_status"] == "expired"
        assert row_expired["box_provisioned"] is False
        assert row_expired["box_connected"] is False
        assert row_expired["active_missions"] == 0

        row_none = _row_for(body["rows"], none_id)
        assert row_none["license_status"] == "none"
        assert row_none["license_tier"] is None
        assert row_none["active_missions"] == 0

        # Le résumé est GLOBAL (toutes les boxes du cabinet) — d'autres tenants
        # peuvent préexister en base. On teste la cohérence du résumé vis-à-vis des
        # lignes retournées (la logique d'agrégation), pas des comptes absolus.
        rows = body["rows"]
        summary = body["summary"]
        assert summary["clients"] == len(rows)
        assert summary["boxes_connected"] == sum(1 for r in rows if r["box_connected"])
        assert summary["licenses_active"] == sum(1 for r in rows if r["license_status"] == "active")
        assert summary["licenses_expired_or_revoked"] == sum(
            1 for r in rows if r["license_status"] in ("expired", "revoked")
        )
        assert summary["licenses_none"] == sum(1 for r in rows if r["license_status"] == "none")
    finally:
        REGISTRY.pop(str(active_id), None)

    async with factory() as s:
        await _cleanup(s, [active_id, expired_id, none_id, cabinet_id], [admin_id])


@pytest.mark.asyncio
async def test_fleet_expiring_soon() -> None:
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
            expires_at=now + timedelta(days=10),
            created_at=now,
        )
        s.add(grant)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {_admin_jwt(admin_id)}"}
        r_wide = await ac.get("/v1/cortex/fleet", headers=headers, params={"expiring_days": 30})
        r_narrow = await ac.get("/v1/cortex/fleet", headers=headers, params={"expiring_days": 5})

    assert r_wide.status_code == 200, r_wide.text
    assert r_narrow.status_code == 200, r_narrow.text
    wide, narrow = r_wide.json(), r_narrow.json()

    row = _row_for(wide["rows"], tenant_id)
    assert row["license_days_left"] in (9, 10)

    # Le seuil est bien appliqué (résumé cohérent avec les lignes) et notre licence
    # (~10 j) est comptée à 30 j mais pas à 5 j — sans dépendre d'autres tenants.
    def _expiring(body: dict, thr: int) -> int:
        return sum(
            1
            for r in body["rows"]
            if r["license_status"] == "active"
            and r["license_days_left"] is not None
            and r["license_days_left"] <= thr
        )

    assert wide["summary"]["licenses_expiring_soon"] == _expiring(wide, 30)
    assert narrow["summary"]["licenses_expiring_soon"] == _expiring(narrow, 5)
    assert 5 < row["license_days_left"] <= 30

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_fleet_most_recent_license_wins() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    now = datetime.now(UTC)

    async with factory() as s:
        admin = await _make_admin(s)
        client_tenant = _make_client_tenant()
        s.add(client_tenant)
        await s.flush()

        old_active = LicenseGrant(
            tenant_id=client_tenant.id,
            license_id=f"lic-{uuid.uuid4().hex}",
            tier="starter",
            modules=[],
            token="a.b.c",
            issued_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=300),
            created_at=now - timedelta(days=10),
        )
        recent_revoked = LicenseGrant(
            tenant_id=client_tenant.id,
            license_id=f"lic-{uuid.uuid4().hex}",
            tier="full",
            modules=[],
            token="a.b.c",
            issued_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=90),
            revoked_at=now,
            created_at=now,
        )
        s.add_all([old_active, recent_revoked])
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(
            "/v1/cortex/fleet",
            headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
        )
    assert r.status_code == 200, r.text
    row = _row_for(r.json()["rows"], tenant_id)
    assert row["license_status"] == "revoked"
    assert row["license_tier"] == "full"

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


def test_fleet_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/fleet doit retourner 404 (router non monté)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from fastapi.testclient import TestClient

        from zolaos.api.main import create_app

        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/cortex/fleet")
        assert r.status_code == 404
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
