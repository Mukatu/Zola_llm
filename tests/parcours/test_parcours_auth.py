"""Parcours end-to-end — Authentification (login / refresh / logout + RBAC).

Comble un trou : le routeur d'auth de production n'avait aucun test. Nécessite
**Postgres réel** (tables `core.*` à schéma, incompatibles SQLite) → skip sinon.
Chaque test sème son propre utilisateur (email unique) et nettoie derrière lui.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.api.main import create_app
from zolaos.core.rbac import SCOPE_ADMIN_USERS
from zolaos.core.security import hash_password
from zolaos.db.models import User
from zolaos.db.session import get_session_factory, reset_engine_cache


async def _pg_ok(factory) -> bool:  # type: ignore[no-untyped-def]
    try:
        async with factory() as s:
            await s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _seed_user(factory, *, role: str) -> tuple[str, str, uuid.UUID]:  # type: ignore[no-untyped-def]
    email = f"parcours-{uuid.uuid4().hex[:8]}@zolaos.test"
    password = "Secret-Pilote-2026!"
    async with factory() as s:
        u = User(
            email=email,
            display_name="Parcours Auth",
            password_hash=hash_password(password),
            country="cg",
            role=role,
        )
        s.add(u)
        await s.commit()
        uid = u.id
    return email, password, uid


async def _cleanup(factory, uid: uuid.UUID) -> None:  # type: ignore[no-untyped-def]
    async with factory() as s:
        await s.execute(
            text("DELETE FROM core.refresh_tokens WHERE user_id = :id"), {"id": str(uid)}
        )
        await s.execute(text("DELETE FROM core.users WHERE id = :id"), {"id": str(uid)})
        await s.commit()


async def test_parcours_login_refresh_logout() -> None:
    reset_engine_cache()
    factory = get_session_factory()
    if not await _pg_ok(factory):
        pytest.skip("Postgres indisponible (parcours auth nécessite les tables core.*)")

    email, password, uid = await _seed_user(factory, role="admin")
    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Mauvais mot de passe → 401.
            bad = await ac.post("/v1/auth/login", json={"email": email, "password": "faux"})
            assert bad.status_code == 401
            assert bad.json()["detail"] == "invalid_credentials"

            # 2. Login correct → 200, cookies posés, jeton CSRF, rôle/scopes cohérents.
            ok = await ac.post("/v1/auth/login", json={"email": email, "password": password})
            assert ok.status_code == 200
            body = ok.json()
            csrf = body["csrf_token"]
            assert ac.cookies.get("zo_access") is not None
            assert ac.cookies.get("zo_refresh") is not None
            assert body["user"]["role"] == "admin"
            assert SCOPE_ADMIN_USERS in body["user"]["scopes"]

            # 3. Refresh SANS jeton CSRF → 403 (double-submit).
            no_csrf = await ac.post("/v1/auth/refresh")
            assert no_csrf.status_code == 403

            # 4. Refresh AVEC jeton CSRF → 200, nouveau jeton.
            ref = await ac.post("/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
            assert ref.status_code == 200
            csrf2 = ref.json()["csrf_token"]

            # 5. Logout (CSRF requis) → 204.
            out = await ac.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf2})
            assert out.status_code == 204
    finally:
        await _cleanup(factory, uid)


async def test_parcours_rbac_role_client_sans_scope_admin() -> None:
    reset_engine_cache()
    factory = get_session_factory()
    if not await _pg_ok(factory):
        pytest.skip("Postgres indisponible (parcours auth nécessite les tables core.*)")

    email, password, uid = await _seed_user(factory, role="client")
    try:
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ok = await ac.post("/v1/auth/login", json={"email": email, "password": password})
            assert ok.status_code == 200
            scopes = ok.json()["user"]["scopes"]
            # Un rôle "client" ne porte pas le scope d'administration.
            assert SCOPE_ADMIN_USERS not in scopes
    finally:
        await _cleanup(factory, uid)
