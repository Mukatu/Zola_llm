"""Tests endpoint Cortex GET /v1/cortex/audit (journal d'audit cabinet).

Couvre :
- Consultation du journal canonique `audit.log` (écrit via `record_audit`)
  filtrée par `tenant_id` (porteur du marqueur unique du test)
- Filtre par verbe d'événement (`event`)
- Référentiel des actions connues (`GET /v1/cortex/audit/actions`)
- Route 404 en profil box (montée uniquement en profil cortex)

⚠️ `audit.log` est APPEND-ONLY (trigger interdisant DELETE/UPDATE) : on n'y
supprime jamais rien. On isole les événements de chaque test par un
`target_id` (uuid) unique, propagé en `tenant_id` du journal (via
`target_type="tenant"`), et on filtre dessus pour ignorer les lignes
préexistantes ou écrites par d'autres tests.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.api.auth import Principal
from zolaos.audit import record_audit
from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import User
from zolaos.db.session import get_session_factory, reset_engine_cache


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


def _admin_jwt(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=str(user_id),
        settings=get_settings(),
        extra_claims={"scopes": ["cortex", "admin:users"]},
    )


def _admin_principal(user_id: uuid.UUID) -> Principal:
    return Principal(
        user_id=user_id,
        email="admin@polaris.cg",
        tenant_id=None,
        country="cg",
        auth_method="jwt",
        role="admin",
    )


async def _cleanup(session, user_ids: list[uuid.UUID]) -> None:
    # On ne touche jamais à audit.log (append-only) : seuls les users créés
    # pour le test sont nettoyés.
    for uid in user_ids:
        await session.execute(text("DELETE FROM core.users WHERE id = :id"), {"id": str(uid)})
    await session.commit()


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_records_are_listed() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    marker = str(uuid.uuid4())

    async with factory() as s:
        admin = await _make_admin(s)
        actor = _admin_principal(admin.id)

        await record_audit(
            s,
            actor=actor,
            action="license.issued",
            summary="Licence business émise pour le client de test",
            target_type="tenant",
            target_id=marker,
            extra={"tier": "business"},
        )
        await record_audit(
            s,
            actor=actor,
            action="account.created",
            summary="Compte consultant créé",
            target_type="tenant",
            target_id=marker,
        )
        await s.commit()
        admin_id = admin.id

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(
            "/v1/cortex/audit",
            headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            params={"tenant_id": marker, "limit": 500},
        )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2

    issued = next(row for row in rows if row["event"] == "license.issued")
    assert issued["category"] == "security"
    assert issued["actor_id"] == str(admin_id)
    assert issued["tenant_id"] == marker
    assert issued["payload"]["summary"] == "Licence business émise pour le client de test"
    assert issued["payload"]["tier"] == "business"

    async with factory() as s:
        await _cleanup(s, [admin_id])


@pytest.mark.asyncio
async def test_audit_filter_by_event() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    marker = str(uuid.uuid4())

    async with factory() as s:
        admin = await _make_admin(s)
        actor = _admin_principal(admin.id)

        await record_audit(
            s,
            actor=actor,
            action="license.issued",
            summary="Licence émise (filtre événement)",
            target_type="tenant",
            target_id=marker,
        )
        await record_audit(
            s,
            actor=actor,
            action="account.created",
            summary="Compte créé (filtre événement)",
            target_type="tenant",
            target_id=marker,
        )
        await s.commit()
        admin_id = admin.id

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(
            "/v1/cortex/audit",
            headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
            params={"event": "license.issued", "tenant_id": marker, "limit": 500},
        )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["event"] == "license.issued"
    assert rows[0]["tenant_id"] == marker

    async with factory() as s:
        await _cleanup(s, [admin_id])


@pytest.mark.asyncio
async def test_audit_actions_catalogue() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        admin = await _make_admin(s)
        await s.commit()
        admin_id = admin.id

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(
            "/v1/cortex/audit/actions",
            headers={"Authorization": f"Bearer {_admin_jwt(admin_id)}"},
        )
    assert r.status_code == 200, r.text
    actions = r.json()
    assert "license.issued" in actions
    assert "account.created" in actions

    async with factory() as s:
        await _cleanup(s, [admin_id])


def test_audit_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/audit doit retourner 404 (router non monté)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from fastapi.testclient import TestClient

        from zolaos.api.main import create_app

        app = create_app()
        client = TestClient(app)
        r = client.get("/v1/cortex/audit")
        assert r.status_code == 404
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
