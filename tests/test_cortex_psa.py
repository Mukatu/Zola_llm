"""Tests endpoints Cortex /v1/cortex/psa (feuilles de temps → économie → occupation).

Couvre :
- POST time-entries : 201, taux figé selon le grade du consultant
- GET time-entries?mine=true : retrouve la saisie du principal
- PATCH action=submit (propriétaire) puis action=approve (scope admin:users) ;
  approve d'une saisie non soumise → 409
- Édition des champs : propriétaire + draft uniquement ; après submit → 409
- GET engagements/{mission_id} : économie de mission cohérente avec le barème
- GET utilization?period=YYYY-MM : ligne du consultant, occupation/activité
- GET rate-card : barème configuré
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
_RATE_CARD_JSON = '{"senior":{"bill_rate":45000,"cost_rate":18000,"currency":"XAF"}}'

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
def _rate_card_env():
    prev = os.environ.get("PSA_RATE_CARD_JSON")
    os.environ["PSA_RATE_CARD_JSON"] = _RATE_CARD_JSON
    get_settings.cache_clear()
    yield
    if prev is None:
        os.environ.pop("PSA_RATE_CARD_JSON", None)
    else:
        os.environ["PSA_RATE_CARD_JSON"] = prev
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
    """JWT du consultant, porteur des deux scopes (saisie + revue/agrégats admin)."""
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
        text("DELETE FROM core.time_entries WHERE consultant_user_id = :u"),
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
async def test_log_and_list_time_entry() -> None:
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
        r = await ac.post(
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "entry_date": "2026-07-01",
                "minutes": 480,
                "billable": True,
                "activity": "audit conformité",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["consultant_user_id"] == str(consultant_id)
        assert body["mission_id"] == str(mission_id)
        assert body["status"] == "draft"
        assert body["bill_rate"] == 45000
        assert body["cost_rate"] == 18000
        assert body["honoraires"] == 360000
        assert body["cost"] == 144000

        r_list = await ac.get(
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            params={"mine": "true"},
        )
        assert r_list.status_code == 200, r_list.text
        entries = r_list.json()
        assert any(e["id"] == body["id"] for e in entries)

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_submit_then_approve_flow() -> None:
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
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "entry_date": "2026-07-02",
                "minutes": 240,
                "billable": True,
            },
        )
        assert r_create.status_code == 201, r_create.text
        entry_id = r_create.json()["id"]

        r_submit = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"action": "submit"},
        )
        assert r_submit.status_code == 200, r_submit.text
        assert r_submit.json()["status"] == "submitted"

        r_approve = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"action": "approve"},
        )
        assert r_approve.status_code == 200, r_approve.text
        assert r_approve.json()["status"] == "approved"

        # Une saisie déjà approuvée (donc plus "submitted") ne peut être re-approuvée.
        r_approve_again = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"action": "approve"},
        )
        assert r_approve_again.status_code == 409
        assert r_approve_again.json()["detail"] == "not_submitted"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_edit_only_owner_draft() -> None:
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
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "entry_date": "2026-07-03",
                "minutes": 120,
                "billable": True,
            },
        )
        assert r_create.status_code == 201, r_create.text
        entry_id = r_create.json()["id"]

        # Édition en brouillon (propriétaire) : OK.
        r_edit = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"minutes": 300},
        )
        assert r_edit.status_code == 200, r_edit.text
        assert r_edit.json()["minutes"] == 300

        r_submit = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"action": "submit"},
        )
        assert r_submit.status_code == 200, r_submit.text

        # Édition après soumission : refusée (plus draft).
        r_edit_after = await ac.patch(
            f"/v1/cortex/psa/time-entries/{entry_id}",
            headers=_headers(token),
            json={"minutes": 400},
        )
        assert r_edit_after.status_code == 409
        assert r_edit_after.json()["detail"] == "only_owner_can_edit_draft"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_engagement_economics() -> None:
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
        entry_ids: list[str] = []
        for entry_date, minutes in (("2026-07-01", 480), ("2026-07-02", 120)):
            r = await ac.post(
                "/v1/cortex/psa/time-entries",
                headers=_headers(token),
                json={
                    "mission_id": str(mission_id),
                    "entry_date": entry_date,
                    "minutes": minutes,
                    "billable": True,
                },
            )
            assert r.status_code == 201, r.text
            entry_ids.append(r.json()["id"])

        # Approuve les deux saisies (submit puis approve).
        for entry_id in entry_ids:
            r_submit = await ac.patch(
                f"/v1/cortex/psa/time-entries/{entry_id}",
                headers=_headers(token),
                json={"action": "submit"},
            )
            assert r_submit.status_code == 200, r_submit.text
            r_approve = await ac.patch(
                f"/v1/cortex/psa/time-entries/{entry_id}",
                headers=_headers(token),
                json={"action": "approve"},
            )
            assert r_approve.status_code == 200, r_approve.text

        r_econ = await ac.get(
            f"/v1/cortex/psa/engagements/{mission_id}",
            headers=_headers(token),
        )
        assert r_econ.status_code == 200, r_econ.text
        econ = r_econ.json()

    # 480 + 120 = 600 min @ 45000/18000 (tout facturable et approuvé).
    assert econ["minutes"] == 600
    assert econ["billable_minutes"] == 600
    assert econ["honoraires"] == 450000
    assert econ["honoraires_wip"] == 450000
    assert econ["cost"] == 180000
    assert econ["margin"] == 270000
    assert econ["margin_pct"] == round(270000 / 450000 * 100)

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_utilization_period() -> None:
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
        r = await ac.post(
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "entry_date": "2026-06-15",
                "minutes": 480,
                "billable": True,
            },
        )
        assert r.status_code == 201, r.text

        r_util = await ac.get(
            "/v1/cortex/psa/utilization",
            headers=_headers(token),
            params={"period": "2026-06"},
        )
        assert r_util.status_code == 200, r_util.text
        rows = r_util.json()

    row = next(x for x in rows if x["consultant_user_id"] == str(consultant_id))
    assert row["worked_minutes"] == 480
    assert row["billable_minutes"] == 480
    assert row["available_minutes"] > 0
    assert row["occupation_pct"] is not None
    assert row["activity_pct"] is not None

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_rate_card_endpoint() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, _mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.get("/v1/cortex/psa/rate-card", headers=_headers(token))
    assert r.status_code == 200, r.text
    card = r.json()
    assert "senior" in card
    assert card["senior"]["bill_rate"] == 45000
    assert card["senior"]["cost_rate"] == 18000

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_psa_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/psa n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/psa") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/psa") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
