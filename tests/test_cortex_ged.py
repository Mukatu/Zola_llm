"""Tests endpoints Cortex /v1/cortex/ged (modèles de livrables + documents produits).

Couvre :
- POST/GET/PATCH /templates (mutations réservées admin) : CRUD + is_active
- POST /deliverables : contenu semé du squelette du modèle quand `template_id` fourni
- PATCH /deliverables/{id} : version incrémentée seulement si le contenu change ;
  changement de statut sans effet sur la version ; statut invalide → 422
- GET /deliverables (liste) sans le contenu vs GET /deliverables/{id} avec le contenu
- 404 mission/template inexistants
- Routes 404 en profil box (montées uniquement profil cortex)
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
from zolaos.db.models import Mission, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache

_CSRF = "test-csrf-token"

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
# Helpers : setup cabinet/client/consultant + mission, JWT, client HTTP CSRF
# ----------------------------------------------------------------------------


async def _setup_mission(session) -> tuple[Tenant, Tenant, User, Mission]:
    cabinet = Tenant(
        name=f"polaris-test-{uuid.uuid4().hex[:6]}",
        tenant_type="cabinet",
        country="cg",
    )
    client = Tenant(
        name=f"client-test-{uuid.uuid4().hex[:6]}",
        tenant_type="client",
        country="cg",
    )
    session.add_all([cabinet, client])
    await session.flush()

    consultant = User(
        email=f"consultant-{uuid.uuid4().hex[:6]}@polaris.cg",
        display_name="Consultant Test",
        password_hash=hash_password("test-password-123!"),
        country="cg",
        tenant_uuid=cabinet.id,
    )
    session.add(consultant)
    await session.flush()

    now = datetime.now(UTC)
    mission = Mission(
        cabinet_tenant_id=cabinet.id,
        client_tenant_id=client.id,
        offre="audit",
        consultant_user_id=consultant.id,
        started_at=now,
        expires_at=now + timedelta(hours=1),
        status="active",
        scope_tags=["country:cg"],
    )
    session.add(mission)
    await session.flush()
    return cabinet, client, consultant, mission


def _jwt_for(user_id: uuid.UUID) -> str:
    """JWT du consultant, porteur des deux scopes (modèles-admin + livrables-consultant)."""
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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": _CSRF}


async def _cleanup(session, cabinet: Tenant, client: Tenant, consultant: User) -> None:
    await session.execute(
        text(
            "DELETE FROM core.deliverables WHERE mission_id IN (SELECT id FROM core.missions WHERE cabinet_tenant_id = :c)"
        ),
        {"c": str(cabinet.id)},
    )
    await session.execute(
        text("DELETE FROM core.deliverable_templates WHERE created_by_user_id = :u"),
        {"u": str(consultant.id)},
    )
    await session.execute(
        text("DELETE FROM core.missions WHERE cabinet_tenant_id = :c"), {"c": str(cabinet.id)}
    )
    await session.execute(text("DELETE FROM core.users WHERE id = :id"), {"id": str(consultant.id)})
    await session.execute(
        text("DELETE FROM core.tenants WHERE id IN (:c1, :c2)"),
        {"c1": str(cabinet.id), "c2": str(client.id)},
    )
    await session.commit()


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_template_crud() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, _mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_create = await ac.post(
            "/v1/cortex/ged/templates",
            headers=_headers(token),
            json={
                "name": "Rapport audit",
                "offre": "audit",
                "sections": [
                    {"title": "Contexte", "guidance": "g"},
                    {"title": "Constats"},
                ],
            },
        )
        assert r_create.status_code == 201, r_create.text
        tpl = r_create.json()
        assert tpl["name"] == "Rapport audit"
        assert tpl["is_active"] is True
        template_id = tpl["id"]

        r_list = await ac.get(
            "/v1/cortex/ged/templates", headers=_headers(token), params={"offre": "audit"}
        )
        assert r_list.status_code == 200, r_list.text
        assert any(t["id"] == template_id for t in r_list.json())

        r_get = await ac.get(f"/v1/cortex/ged/templates/{template_id}", headers=_headers(token))
        assert r_get.status_code == 200, r_get.text
        assert r_get.json()["id"] == template_id

        r_patch = await ac.patch(
            f"/v1/cortex/ged/templates/{template_id}",
            headers=_headers(token),
            json={"is_active": False},
        )
        assert r_patch.status_code == 200, r_patch.text
        assert r_patch.json()["is_active"] is False

        r_active = await ac.get(
            "/v1/cortex/ged/templates",
            headers=_headers(token),
            params={"active_only": "true"},
        )
        assert r_active.status_code == 200, r_active.text
        assert not any(t["id"] == template_id for t in r_active.json())

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_deliverable_from_template_seeds_content() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_tpl = await ac.post(
            "/v1/cortex/ged/templates",
            headers=_headers(token),
            json={
                "name": "Rapport audit",
                "sections": [{"title": "Contexte", "guidance": "g"}],
            },
        )
        assert r_tpl.status_code == 201, r_tpl.text
        template_id = r_tpl.json()["id"]

        r_del = await ac.post(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            json={"mission_id": str(mission_id), "template_id": template_id, "title": "Rapport X"},
        )
        assert r_del.status_code == 201, r_del.text
        deliverable = r_del.json()
        assert deliverable["status"] == "draft"
        assert deliverable["version"] == 1
        assert "# Rapport X" in deliverable["content"]
        assert "## Contexte" in deliverable["content"]

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_deliverable_version_bumps_on_content_change() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_create = await ac.post(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            json={"mission_id": str(mission_id), "title": "Note"},
        )
        assert r_create.status_code == 201, r_create.text
        deliverable_id = r_create.json()["id"]

        r_v2 = await ac.patch(
            f"/v1/cortex/ged/deliverables/{deliverable_id}",
            headers=_headers(token),
            json={"content": "# Note\n\ncontenu v2\n"},
        )
        assert r_v2.status_code == 200, r_v2.text
        assert r_v2.json()["version"] == 2

        r_v2_bis = await ac.patch(
            f"/v1/cortex/ged/deliverables/{deliverable_id}",
            headers=_headers(token),
            json={"content": "# Note\n\ncontenu v2\n"},
        )
        assert r_v2_bis.status_code == 200, r_v2_bis.text
        assert r_v2_bis.json()["version"] == 2

        r_status = await ac.patch(
            f"/v1/cortex/ged/deliverables/{deliverable_id}",
            headers=_headers(token),
            json={"status": "review"},
        )
        assert r_status.status_code == 200, r_status.text
        assert r_status.json()["status"] == "review"
        assert r_status.json()["version"] == 2

        r_bad_status = await ac.patch(
            f"/v1/cortex/ged/deliverables/{deliverable_id}",
            headers=_headers(token),
            json={"status": "archived"},
        )
        assert r_bad_status.status_code == 422
        assert "invalid_status" in r_bad_status.json()["detail"]

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_deliverable_list_has_no_content_detail_has() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_create = await ac.post(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            json={"mission_id": str(mission_id), "title": "Note"},
        )
        assert r_create.status_code == 201, r_create.text
        deliverable_id = r_create.json()["id"]

        r_list = await ac.get(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            params={"mission_id": str(mission_id)},
        )
        assert r_list.status_code == 200, r_list.text
        items = r_list.json()
        assert any(d["id"] == deliverable_id for d in items)
        for d in items:
            assert "content" not in d

        r_get = await ac.get(
            f"/v1/cortex/ged/deliverables/{deliverable_id}", headers=_headers(token)
        )
        assert r_get.status_code == 200, r_get.text
        assert "content" in r_get.json()

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_ged_404s() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_no_mission = await ac.post(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            json={"mission_id": str(uuid.uuid4()), "title": "Note"},
        )
        assert r_no_mission.status_code == 404
        assert r_no_mission.json()["detail"] == "mission_not_found"

        r_no_template = await ac.post(
            "/v1/cortex/ged/deliverables",
            headers=_headers(token),
            json={"mission_id": str(mission_id), "template_id": str(uuid.uuid4()), "title": "Note"},
        )
        assert r_no_template.status_code == 404
        assert r_no_template.json()["detail"] == "template_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_ged_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/ged n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/ged") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/ged") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
