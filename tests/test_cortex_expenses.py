"""Tests endpoints Cortex /v1/cortex/expenses (notes de frais → intégration facturation).

Couvre :
- POST "" : 201 en brouillon ; catégorie invalide → 422
- PATCH action=submit (propriétaire) puis action=approve (scope admin:users)
- Édition des champs : propriétaire + draft uniquement ; après submit → 409
- GET mission/{mission_id}/summary (admin) : synthèse cohérente avec summarize_expenses
- Intégration facturation : un frais facturable approuvé devient un débours
  refacturable repris par la facture d'honoraires (aux côtés des temps) ; l'annulation
  de la facture libère aussi les frais
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
from zolaos.db.models import Expense, Mission, Tenant, TimeEntry, User
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
        text("DELETE FROM core.expenses WHERE consultant_user_id = :u"),
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
async def test_log_submit_approve_expense() -> None:
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
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-01",
                "category": "transport",
                "amount": 50000,
                "billable": True,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["consultant_user_id"] == str(consultant_id)
        assert body["mission_id"] == str(mission_id)
        assert body["category"] == "transport"
        assert body["amount"] == 50000
        assert body["billable"] is True
        assert body["status"] == "draft"
        assert body["invoice_id"] is None
        expense_id = body["id"]

        # Catégorie inconnue au référentiel fermé → 422.
        r_invalid = await ac.post(
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-01",
                "category": "inexistante",
                "amount": 1000,
            },
        )
        assert r_invalid.status_code == 422, r_invalid.text
        assert "invalid_category" in r_invalid.json()["detail"]

        r_submit = await ac.patch(
            f"/v1/cortex/expenses/{expense_id}",
            headers=_headers(token),
            json={"action": "submit"},
        )
        assert r_submit.status_code == 200, r_submit.text
        assert r_submit.json()["status"] == "submitted"

        r_approve = await ac.patch(
            f"/v1/cortex/expenses/{expense_id}",
            headers=_headers(token),
            json={"action": "approve"},
        )
        assert r_approve.status_code == 200, r_approve.text
        assert r_approve.json()["status"] == "approved"

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
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-02",
                "category": "repas",
                "amount": 10000,
                "billable": False,
            },
        )
        assert r_create.status_code == 201, r_create.text
        expense_id = r_create.json()["id"]

        # Édition en brouillon (propriétaire) : OK.
        r_edit = await ac.patch(
            f"/v1/cortex/expenses/{expense_id}",
            headers=_headers(token),
            json={"amount": 15000},
        )
        assert r_edit.status_code == 200, r_edit.text
        assert r_edit.json()["amount"] == 15000

        r_submit = await ac.patch(
            f"/v1/cortex/expenses/{expense_id}",
            headers=_headers(token),
            json={"action": "submit"},
        )
        assert r_submit.status_code == 200, r_submit.text

        # Édition après soumission : refusée (plus draft).
        r_edit_after = await ac.patch(
            f"/v1/cortex/expenses/{expense_id}",
            headers=_headers(token),
            json={"amount": 20000},
        )
        assert r_edit_after.status_code == 409
        assert r_edit_after.json()["detail"] == "only_owner_can_edit_draft"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_expenses_summary() -> None:
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
        # transport facturable, ira jusqu'à approved (refacturable).
        r1 = await ac.post(
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-01",
                "category": "transport",
                "amount": 50000,
                "billable": True,
            },
        )
        assert r1.status_code == 201, r1.text
        id1 = r1.json()["id"]
        for action in ("submit", "approve"):
            r = await ac.patch(
                f"/v1/cortex/expenses/{id1}",
                headers=_headers(token),
                json={"action": action},
            )
            assert r.status_code == 200, r.text

        # repas non facturable, restera en brouillon (compte quand même, non rejeté).
        r2 = await ac.post(
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-02",
                "category": "repas",
                "amount": 30000,
                "billable": False,
            },
        )
        assert r2.status_code == 201, r2.text

        # fournitures facturable mais rejetée : exclue de la synthèse.
        r3 = await ac.post(
            "/v1/cortex/expenses",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "expense_date": "2026-07-03",
                "category": "fournitures",
                "amount": 99999,
                "billable": True,
            },
        )
        assert r3.status_code == 201, r3.text
        id3 = r3.json()["id"]
        r_submit3 = await ac.patch(
            f"/v1/cortex/expenses/{id3}",
            headers=_headers(token),
            json={"action": "submit"},
        )
        assert r_submit3.status_code == 200, r_submit3.text
        r_reject3 = await ac.patch(
            f"/v1/cortex/expenses/{id3}",
            headers=_headers(token),
            json={"action": "reject"},
        )
        assert r_reject3.status_code == 200, r_reject3.text
        assert r_reject3.json()["status"] == "rejected"

        r_summary = await ac.get(
            f"/v1/cortex/expenses/mission/{mission_id}/summary",
            headers=_headers(token),
        )
        assert r_summary.status_code == 200, r_summary.text
        summary = r_summary.json()

    assert summary["mission_id"] == str(mission_id)
    assert summary["count"] == 2  # la rejetée n'est pas comptée
    assert summary["total"] == 80000  # 50000 + 30000
    assert summary["billable_total"] == 50000
    assert summary["refacturable_approved"] == 50000
    assert summary["by_category"] == {"transport": 50000, "repas": 30000}
    assert summary["currency"] == "XAF"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_invoice_bundles_billable_expenses() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)

        # 240 min facturables approuvées @ 45000/18000 → 180000 d'honoraires.
        time_entry = TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date(2026, 7, 1),
            minutes=240,
            billable=True,
            activity="audit conformité",
            status="approved",
            bill_rate=45000,
            cost_rate=18000,
        )
        # Frais facturable approuvé : débours refacturable (repris par la facture).
        expense_billable = Expense(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            expense_date=date(2026, 7, 1),
            category="transport",
            amount=50000,
            billable=True,
            status="approved",
        )
        # Frais non facturable approuvé : un coût, mais pas un débours (exclu de la facture).
        expense_non_billable = Expense(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            expense_date=date(2026, 7, 2),
            category="repas",
            amount=30000,
            billable=False,
            status="approved",
        )
        s.add_all([time_entry, expense_billable, expense_non_billable])
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
        )
        expense_billable_id, expense_non_billable_id = (
            expense_billable.id,
            expense_non_billable.id,
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
        invoice = r_create.json()
        # 180000 (temps) + 50000 (frais transport refacturable) ; le repas 30000 exclu.
        assert invoice["amount"] == 230000
        invoice_id = invoice["id"]

        r_detail = await ac.get(
            f"/v1/cortex/invoices/{invoice_id}",
            headers=_headers(token),
        )
        assert r_detail.status_code == 200, r_detail.text
        detail = r_detail.json()

        expense_ids_on_invoice = {e["id"] for e in detail["expenses"]}
        assert str(expense_billable_id) in expense_ids_on_invoice
        assert str(expense_non_billable_id) not in expense_ids_on_invoice
        assert len(detail["entries"]) == 1

        r_cancel = await ac.post(
            f"/v1/cortex/invoices/{invoice_id}/cancel",
            headers=_headers(token),
        )
        assert r_cancel.status_code == 200, r_cancel.text
        assert r_cancel.json()["status"] == "cancelled"

    async with factory() as s:
        row = (
            await s.execute(
                text("SELECT invoice_id FROM core.expenses WHERE id = :id"),
                {"id": str(expense_billable_id)},
            )
        ).scalar_one()
        assert row is None  # libéré par l'annulation

        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_expenses_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/expenses n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/expenses") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/expenses") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
