"""Tests endpoints Cortex /v1/cortex/invoices (facturation d'honoraires, aval PSA).

Couvre :
- POST "" : regroupe les feuilles de temps facturables approuvées non facturées
  d'une mission en un brouillon ; 409 s'il n'y a rien à facturer
- POST /{id}/issue puis /{id}/pay : cycle draft → issued → paid ; re-encaissement → 409
- POST /{id}/cancel : libère les saisies rattachées (re-facturables)
- GET /aging : échéancier des factures émises non payées
- GET /{id} : détail avec les saisies rattachées
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
from zolaos.db.models import Mission, Tenant, TimeEntry, User
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
# Helpers : setup cabinet/client/consultant + mission, saisies, JWT, client HTTP CSRF
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


async def _add_billable_entries(
    session, mission: Mission, consultant: User, count: int = 2
) -> list[TimeEntry]:
    """Saisies déjà approuvées et facturables, prêtes à être regroupées en facture."""
    entries = []
    for i in range(count):
        entry = TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date(2026, 7, 1 + i),
            minutes=240,
            billable=True,
            activity="audit conformité",
            status="approved",
            bill_rate=45000,
            cost_rate=18000,
        )
        session.add(entry)
        entries.append(entry)
    await session.flush()
    return entries


def _jwt_for(user_id: uuid.UUID) -> str:
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
        text("DELETE FROM core.invoices WHERE client_tenant_id = :c"), {"c": str(client.id)}
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
async def test_create_invoice_bundles_approved_entries() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _add_billable_entries(s, mission, consultant)
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
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["amount"] == 360000
        assert body["status"] == "draft"
        assert body["mission_id"] == str(mission_id)
        invoice_id = body["id"]

        # Plus rien à facturer : les deux saisies sont déjà rattachées.
        r_again = await ac.post(
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_again.status_code == 409
        assert r_again.json()["detail"] == "nothing_to_invoice"

    async with factory() as s:
        rows = (
            (
                await s.execute(
                    text("SELECT invoice_id FROM core.time_entries WHERE mission_id = :m"),
                    {"m": str(mission_id)},
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert all(str(row) == invoice_id for row in rows)

        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_issue_pay_cycle() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _add_billable_entries(s, mission, consultant)
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
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_create.status_code == 201, r_create.text
        invoice_id = r_create.json()["id"]

        r_issue = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/issue",
            headers=_headers(token),
            json={"due_days": 30},
        )
        assert r_issue.status_code == 200, r_issue.text
        issued = r_issue.json()
        assert issued["status"] == "issued"
        assert issued["due_date"] is not None

        r_pay = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/pay",
            headers=_headers(token),
        )
        assert r_pay.status_code == 200, r_pay.text
        assert r_pay.json()["status"] == "paid"

        r_pay_again = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/pay",
            headers=_headers(token),
        )
        assert r_pay_again.status_code == 409
        assert "not_issued" in r_pay_again.json()["detail"]

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_cancel_releases_entries() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _add_billable_entries(s, mission, consultant)
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
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_create.status_code == 201, r_create.text
        invoice_id = r_create.json()["id"]

        r_cancel = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/cancel",
            headers=_headers(token),
        )
        assert r_cancel.status_code == 200, r_cancel.text
        assert r_cancel.json()["status"] == "cancelled"

    async with factory() as s:
        rows = (
            (
                await s.execute(
                    text("SELECT invoice_id FROM core.time_entries WHERE mission_id = :m"),
                    {"m": str(mission_id)},
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        assert all(row is None for row in rows)

    async with _client(app) as ac:
        # Les saisies libérées peuvent de nouveau être regroupées en facture.
        r_recreate = await ac.post(
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_recreate.status_code == 201, r_recreate.text
        assert r_recreate.json()["amount"] == 360000

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_aging_lists_issued() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _add_billable_entries(s, mission, consultant)
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
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_create.status_code == 201, r_create.text
        invoice_id = r_create.json()["id"]
        number = r_create.json()["number"]

        r_issue = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/issue",
            headers=_headers(token),
            json={"due_days": 0},
        )
        assert r_issue.status_code == 200, r_issue.text

        r_aging = await ac.get("/v1/cortex/invoices/aging", headers=_headers(token))
        assert r_aging.status_code == 200, r_aging.text
        aging = r_aging.json()

    line = next(x for x in aging["invoices"] if x["number"] == number)
    assert line["amount"] == 360000
    assert line["bucket"] in aging["buckets"]
    assert aging["total_outstanding"] >= line["amount"]

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_detail_lists_entries() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _add_billable_entries(s, mission, consultant)
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
            "/v1/cortex/invoices",
            headers=_headers(token),
            json={"mission_id": str(mission_id)},
        )
        assert r_create.status_code == 201, r_create.text
        invoice_id = r_create.json()["id"]

        r_detail = await ac.get(
            f"/v1/cortex/invoices/{invoice_id}",
            headers=_headers(token),
        )
        assert r_detail.status_code == 200, r_detail.text
        detail = r_detail.json()

    assert len(detail["entries"]) == 2
    assert all(e["honoraires"] == 180000 for e in detail["entries"])
    assert all(e["consultant_user_id"] == str(consultant_id) for e in detail["entries"])

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_invoice_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/invoices n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/invoices") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/invoices") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
