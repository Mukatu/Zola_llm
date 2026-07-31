"""Tests endpoints Cortex /v1/cortex/staffing (affectations & plan de charge).

Couvre :
- POST "" : upsert — normalise week_start au lundi, met à jour (pas de doublon) si
  même consultant × mission × semaine ; 404 si consultant/mission inexistant
- DELETE /{id} : 204 ; 404 si absent
- GET /load : grille consultant × semaine (charge, sur-affectation, capacité)
- Routes 404 en profil box (montées uniquement profil cortex)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta

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
# Helpers : setup cabinet/client/consultant + mission, JWT admin, client HTTP CSRF
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
        grade="senior",
    )
    session.add(consultant)
    await session.flush()

    now = datetime.now(UTC)
    mission = Mission(
        cabinet_tenant_id=cabinet.id,
        client_tenant_id=client.id,
        offre="conformite_rh",
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
    """JWT admin (scopes cortex + admin:users), requis par le router staffing."""
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
        text("DELETE FROM core.assignments WHERE consultant_user_id = :u"),
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
async def test_upsert_normalizes_week_and_updates() -> None:
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
        # Vendredi 2026-07-31 : la semaine normalisée est celle du lundi 2026-07-27.
        r_create = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(mission_id),
                "week_start": "2026-07-31",
                "allocated_minutes": 1200,
            },
        )
        assert r_create.status_code == 201, r_create.text
        body = r_create.json()
        assert body["week_start"] == "2026-07-27"
        assert body["allocated_minutes"] == 1200
        assignment_id = body["id"]

        # Re-poste sur la même semaine (autre date de cette même semaine) : upsert.
        r_update = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(mission_id),
                "week_start": "2026-07-27",
                "allocated_minutes": 2000,
            },
        )
        assert r_update.status_code == 201, r_update.text
        updated = r_update.json()
        assert updated["id"] == assignment_id
        assert updated["week_start"] == "2026-07-27"
        assert updated["allocated_minutes"] == 2000

        r_list = await ac.get(
            "/v1/cortex/staffing",
            headers=_headers(token),
            params={"consultant_user_id": str(consultant_id), "mission_id": str(mission_id)},
        )
        assert r_list.status_code == 200, r_list.text
        rows = r_list.json()
        assert len(rows) == 1
        assert rows[0]["allocated_minutes"] == 2000

        # Consultant inexistant.
        r_no_consultant = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(uuid.uuid4()),
                "mission_id": str(mission_id),
                "week_start": "2026-07-27",
                "allocated_minutes": 100,
            },
        )
        assert r_no_consultant.status_code == 404
        assert r_no_consultant.json()["detail"] == "consultant_not_found"

        # Mission inexistante.
        r_no_mission = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(uuid.uuid4()),
                "week_start": "2026-07-27",
                "allocated_minutes": 100,
            },
        )
        assert r_no_mission.status_code == 404
        assert r_no_mission.json()["detail"] == "mission_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_delete_assignment() -> None:
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
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(mission_id),
                "week_start": "2026-08-03",
                "allocated_minutes": 600,
            },
        )
        assert r_create.status_code == 201, r_create.text
        assignment_id = r_create.json()["id"]

        r_delete = await ac.delete(
            f"/v1/cortex/staffing/{assignment_id}",
            headers=_headers(token),
        )
        assert r_delete.status_code == 204, r_delete.text

        r_delete_missing = await ac.delete(
            f"/v1/cortex/staffing/{uuid.uuid4()}",
            headers=_headers(token),
        )
        assert r_delete_missing.status_code == 404

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_load_plan_grid() -> None:
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

    week_a = date(2026, 8, 3)  # lundi
    week_b = week_a + timedelta(days=7)

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_a = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(mission_id),
                "week_start": week_a.isoformat(),
                "allocated_minutes": 3000,
            },
        )
        assert r_a.status_code == 201, r_a.text

        r_b = await ac.post(
            "/v1/cortex/staffing",
            headers=_headers(token),
            json={
                "consultant_user_id": str(consultant_id),
                "mission_id": str(mission_id),
                "week_start": week_b.isoformat(),
                "allocated_minutes": 1200,
            },
        )
        assert r_b.status_code == 201, r_b.text

        r_load = await ac.get(
            "/v1/cortex/staffing/load",
            headers=_headers(token),
            params={"from": week_a.isoformat(), "weeks": 2},
        )
        assert r_load.status_code == 200, r_load.text
        payload = r_load.json()

    assert payload["capacity_minutes"] == 2400
    consultant_load = next(
        c for c in payload["consultants"] if c["consultant_user_id"] == str(consultant_id)
    )
    assert len(consultant_load["weeks"]) == 2
    week_a_row = next(w for w in consultant_load["weeks"] if w["week_start"] == week_a.isoformat())
    week_b_row = next(w for w in consultant_load["weeks"] if w["week_start"] == week_b.isoformat())
    assert week_a_row["over_allocated"] is True
    assert week_a_row["load_pct"] == 125
    assert week_b_row["over_allocated"] is False
    assert week_b_row["load_pct"] == 50
    assert consultant_load["over_weeks"] == 1

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_staffing_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/staffing n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/staffing") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/staffing") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
