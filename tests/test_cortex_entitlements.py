"""Tests endpoints Cortex /v1/cortex/entitlements (cockpit de gestion des licences).

Couvre :
- GET  /catalogue           : tiers + modules vendables
- POST ""                   : émission → 201, jeton signé VÉRIFIABLE par la clé publique,
                              persisté, modules effectifs = tier ∪ options
- POST ""                   : renouvellement → la licence précédente passe en revoked
- POST ""                   : 422 tier invalide / module hors catalogue / tenant non-client
- POST ""                   : 503 si clé privée d'émission absente
- POST ""                   : 403 sans scope admin:users ; 403 sans CSRF
- POST /{id}/revoke         : 200 puis 409 (déjà révoquée)
- GET  /tenant/{id}/active  : jeton livré ; 404 après révocation
- GET  ""                   : filtre par tenant
- Routes 404 en profil box
"""

from __future__ import annotations

import os
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import LicenseGrant, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.licensing import verify_entitlement

# --- Paire de clés d'émission dédiée aux tests (générée une fois) -------------
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = (
    _key.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)

_CSRF = "test-csrf-token"


# ----------------------------------------------------------------------------
# Fixtures profil + clé d'émission + reset DB engine
# ----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _cortex_env():
    prev_profile = os.environ.get("ZOLAOS_PROFILE", "box")
    prev_priv = os.environ.get("ENTITLEMENT_PRIVATE_KEY")
    prev_pub = os.environ.get("ENTITLEMENT_PUBLIC_KEY")
    os.environ["ZOLAOS_PROFILE"] = "cortex"
    os.environ["ENTITLEMENT_PRIVATE_KEY"] = _PRIVATE_PEM
    os.environ["ENTITLEMENT_PUBLIC_KEY"] = _PUBLIC_PEM
    get_settings.cache_clear()
    yield
    os.environ["ZOLAOS_PROFILE"] = prev_profile
    for var, prev in (
        ("ENTITLEMENT_PRIVATE_KEY", prev_priv),
        ("ENTITLEMENT_PUBLIC_KEY", prev_pub),
    ):
        if prev is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = prev
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    reset_engine_cache()
    yield
    reset_engine_cache()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def _make_admin_and_client(session) -> tuple[User, Tenant]:
    admin = User(
        email=f"admin-{uuid.uuid4().hex[:6]}@polaris.cg",
        display_name="Admin Test",
        password_hash=hash_password("admin-password-123!"),
        country="cg",
        role="admin",
    )
    client = Tenant(
        name=f"client-{uuid.uuid4().hex[:6]}",
        tenant_type="client",
        country="cg",
    )
    session.add_all([admin, client])
    await session.flush()
    return admin, client


def _admin_jwt(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=str(user_id),
        settings=get_settings(),
        extra_claims={"scopes": ["cortex", "admin:users"]},
    )


def _client(app):  # AsyncClient avec le cookie CSRF posé (double-submit).
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"zo_csrf": _CSRF},
    )


def _headers(token: str, *, csrf: bool = True) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if csrf:
        h["X-CSRF-Token"] = _CSRF
    return h


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
async def test_catalogue_lists_tiers_and_modules() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with _client(app) as ac:
        r = await ac.get(
            "/v1/cortex/entitlements/catalogue", headers=_headers(_admin_jwt(admin_id))
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "erp" in body["tiers"]["starter"]
    assert set(body["tiers"]["full"]) == set(body["modules"])
    assert "code" in body["modules"]

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_issue_grant_signs_persists_and_is_verifiable() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with _client(app) as ac:
        r = await ac.post(
            "/v1/cortex/entitlements",
            headers=_headers(_admin_jwt(admin_id)),
            json={
                "tenant_id": str(tenant_id),
                "tier": "business",
                "modules": ["cyber"],
                "days": 365,
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tier"] == "business"
    assert body["modules"] == ["cyber"]
    assert set(body["effective_modules"]) == {"erp", "sirh", "bi", "crm", "marketing", "cyber"}
    assert body["status"] == "active"
    assert body["token"].count(".") == 2

    # Le jeton émis est VÉRIFIABLE par la clé publique (chaîne de confiance intacte).
    ent = verify_entitlement(body["token"], public_key_pem=_PUBLIC_PEM)
    assert ent.tenant_id == str(tenant_id)
    assert ent.tier == "business"
    assert set(ent.effective_modules()) == {"erp", "sirh", "bi", "crm", "marketing", "cyber"}

    # Persisté en base.
    async with factory() as s:
        g = await s.scalar(select(LicenseGrant).where(LicenseGrant.tenant_id == tenant_id))
        assert g is not None
        assert g.tier == "business"
        assert g.revoked_at is None
        assert g.issued_by_user_id == admin_id

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_issue_supersedes_prior_active() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with _client(app) as ac:
        r1 = await ac.post(
            "/v1/cortex/entitlements",
            headers=_headers(_admin_jwt(admin_id)),
            json={"tenant_id": str(tenant_id), "tier": "starter", "days": 30},
        )
        assert r1.status_code == 201
        r2 = await ac.post(
            "/v1/cortex/entitlements",
            headers=_headers(_admin_jwt(admin_id)),
            json={"tenant_id": str(tenant_id), "tier": "full", "days": 365},
        )
        assert r2.status_code == 201

        # Une seule licence active : la 1re a été révoquée par le renouvellement.
        rl = await ac.get(
            "/v1/cortex/entitlements",
            headers=_headers(_admin_jwt(admin_id)),
            params={"tenant_id": str(tenant_id), "active_only": "true"},
        )
    assert rl.status_code == 200
    active = rl.json()
    assert len(active) == 1
    assert active[0]["tier"] == "full"

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_issue_rejects_bad_inputs() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        cabinet = Tenant(name=f"cab-{uuid.uuid4().hex[:6]}", tenant_type="cabinet", country="cg")
        s.add(cabinet)
        await s.commit()
        admin_id, tenant_id, cabinet_id = admin.id, client_tenant.id, cabinet.id

    app = create_app()
    async with _client(app) as ac:
        h = _headers(_admin_jwt(admin_id))
        # tier invalide
        r_tier = await ac.post(
            "/v1/cortex/entitlements",
            headers=h,
            json={"tenant_id": str(tenant_id), "tier": "platinum", "days": 30},
        )
        assert r_tier.status_code == 422
        assert "invalid_tier" in r_tier.json()["detail"]
        # module hors catalogue
        r_mod = await ac.post(
            "/v1/cortex/entitlements",
            headers=h,
            json={
                "tenant_id": str(tenant_id),
                "tier": "starter",
                "modules": ["teleportation"],
                "days": 30,
            },
        )
        assert r_mod.status_code == 422
        assert "unknown_modules" in r_mod.json()["detail"]
        # tenant cabinet (pas client)
        r_cab = await ac.post(
            "/v1/cortex/entitlements",
            headers=h,
            json={"tenant_id": str(cabinet_id), "tier": "starter", "days": 30},
        )
        assert r_cab.status_code == 422
        assert "tenant_must_be_client" in r_cab.json()["detail"]

    async with factory() as s:
        await _cleanup(s, [tenant_id, cabinet_id], [admin_id])


@pytest.mark.asyncio
async def test_issue_without_signing_key_returns_503() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    # Retire la clé privée d'émission : le cockpit doit refuser proprement.
    os.environ.pop("ENTITLEMENT_PRIVATE_KEY", None)
    get_settings.cache_clear()
    try:
        app = create_app()
        async with _client(app) as ac:
            r = await ac.post(
                "/v1/cortex/entitlements",
                headers=_headers(_admin_jwt(admin_id)),
                json={"tenant_id": str(tenant_id), "tier": "starter", "days": 30},
            )
        assert r.status_code == 503
        assert r.json()["detail"] == "signing_key_not_configured"
    finally:
        os.environ["ENTITLEMENT_PRIVATE_KEY"] = _PRIVATE_PEM
        get_settings.cache_clear()

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


@pytest.mark.asyncio
async def test_issue_requires_admin_scope_and_csrf() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        # Un compte SANS scope admin (consultant).
        consultant = User(
            email=f"cons-{uuid.uuid4().hex[:6]}@polaris.cg",
            display_name="Consultant",
            password_hash=hash_password("x-123456789"),
            country="cg",
            role="consultant",
        )
        s.add(consultant)
        await s.commit()
        admin_id, tenant_id, cons_id = admin.id, client_tenant.id, consultant.id

    app = create_app()
    async with _client(app) as ac:
        # Sans scope admin:users → 403.
        non_admin = create_access_token(
            subject=str(cons_id), settings=get_settings(), extra_claims={"scopes": ["cortex"]}
        )
        r_forbidden = await ac.post(
            "/v1/cortex/entitlements",
            headers=_headers(non_admin),
            json={"tenant_id": str(tenant_id), "tier": "starter", "days": 30},
        )
        assert r_forbidden.status_code == 403
        # Admin mais SANS jeton CSRF → 403 csrf_failed.
        r_csrf = await ac.post(
            "/v1/cortex/entitlements",
            headers=_headers(_admin_jwt(admin_id), csrf=False),
            json={"tenant_id": str(tenant_id), "tier": "starter", "days": 30},
        )
        assert r_csrf.status_code == 403
        assert r_csrf.json()["detail"] == "csrf_failed"

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id, cons_id])


@pytest.mark.asyncio
async def test_revoke_and_active_delivery_flow() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin, client_tenant = await _make_admin_and_client(s)
        await s.commit()
        admin_id, tenant_id = admin.id, client_tenant.id

    app = create_app()
    async with _client(app) as ac:
        h = _headers(_admin_jwt(admin_id))
        r_issue = await ac.post(
            "/v1/cortex/entitlements",
            headers=h,
            json={"tenant_id": str(tenant_id), "tier": "business", "days": 90},
        )
        assert r_issue.status_code == 201
        grant_id = r_issue.json()["id"]

        # Livraison : la licence active du tenant + son jeton.
        r_active = await ac.get(f"/v1/cortex/entitlements/tenant/{tenant_id}/active", headers=h)
        assert r_active.status_code == 200
        assert r_active.json()["token"].count(".") == 2

        # Révocation : 200 puis 409.
        r_rev = await ac.post(f"/v1/cortex/entitlements/{grant_id}/revoke", headers=h)
        assert r_rev.status_code == 200
        assert r_rev.json()["status"] == "revoked"
        r_rev2 = await ac.post(f"/v1/cortex/entitlements/{grant_id}/revoke", headers=h)
        assert r_rev2.status_code == 409
        assert r_rev2.json()["detail"] == "already_revoked"

        # Plus aucune licence vivante à livrer → 404.
        r_active2 = await ac.get(f"/v1/cortex/entitlements/tenant/{tenant_id}/active", headers=h)
        assert r_active2.status_code == 404
        assert r_active2.json()["detail"] == "no_active_license"

    async with factory() as s:
        await _cleanup(s, [tenant_id], [admin_id])


def test_entitlement_routes_not_mounted_in_box_profile() -> None:
    """En profil box, /v1/cortex/entitlements/* doit retourner 404 (router non monté)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from fastapi.testclient import TestClient

        from zolaos.api.main import create_app

        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/cortex/entitlements/catalogue")
        assert r.status_code == 404
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
