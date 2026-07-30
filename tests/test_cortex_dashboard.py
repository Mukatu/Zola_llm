"""Tests endpoint Cortex /v1/cortex/dashboard (KPI de pilotage cabinet, capstone).

Couvre :
- GET dashboard?period=YYYY-MM : métriques bornées à la période (honoraires,
  coût, marge, heures, consultants actifs, facturé/encaissé du mois) — isolées
  sur un mois passé distinctif, assertions exactes
- GET dashboard : métriques globales (snapshots non bornés à la période :
  missions actives, WIP, créances, pipeline commercial) — assertions en
  minoration (>=), car la base peut contenir d'autres données
- Période invalide → 422
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
from zolaos.db.models import Invoice, Mission, Opportunity, Tenant, TimeEntry, User
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
# Helpers : setup cabinet/client/consultant + mission + JVM des KPI, JWT
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


async def _seed_dashboard_data(
    session, cabinet: Tenant, client: Tenant, consultant: User, mission: Mission
) -> None:
    """Seed les KPI sur un mois passé distinctif (2017-04), isolé de toute autre donnée.

    Deux saisies facturables approuvées de 240 min en avril 2017 (honoraires
    360000, coût 144000) ; une troisième saisie approuvée+facturable+non
    facturée datée hors période (mars 2017) qui alimente le WIP global sans
    polluer les agrégats bornés à la période. Deux factures d'avril 2017
    (une émise, une payée) ; une opportunité ouverte.
    """
    entries = [
        TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date(2017, 4, 5),
            minutes=240,
            billable=True,
            status="approved",
            bill_rate=45000,
            cost_rate=18000,
        ),
        TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date(2017, 4, 12),
            minutes=240,
            billable=True,
            status="approved",
            bill_rate=45000,
            cost_rate=18000,
        ),
        # Hors période (mars 2017) : ne compte pas dans les agrégats bornés au
        # mois, mais alimente le WIP global (approved + billable + invoice_id
        # NULL, sans filtre de date côté endpoint).
        TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date(2017, 3, 15),
            minutes=60,
            billable=True,
            status="approved",
            bill_rate=45000,
            cost_rate=18000,
        ),
    ]
    session.add_all(entries)

    invoices = [
        Invoice(
            mission_id=mission.id,
            client_tenant_id=client.id,
            number=f"INV-{uuid.uuid4().hex[:8]}",
            status="issued",
            amount=360000,
            issued_date=date(2017, 4, 10),
        ),
        Invoice(
            mission_id=mission.id,
            client_tenant_id=client.id,
            number=f"INV-{uuid.uuid4().hex[:8]}",
            status="paid",
            amount=200000,
            issued_date=date(2017, 4, 5),
            paid_date=date(2017, 4, 20),
        ),
    ]
    session.add_all(invoices)

    opportunity = Opportunity(
        title=f"opportunite-test-{uuid.uuid4().hex[:6]}",
        client_tenant_id=client.id,
        offre="conformite_rh",
        amount_estimate=2_000_000,
        stage="proposal",
        probability=60,
        owner_user_id=consultant.id,
    )
    session.add(opportunity)

    await session.flush()


def _jwt_for(user_id: uuid.UUID) -> str:
    """JWT admin cabinet (scopes cortex + admin:users, requis par le dashboard)."""
    return create_access_token(
        subject=str(user_id),
        settings=get_settings(),
        extra_claims={"scopes": ["cortex", "admin:users"]},
    )


def _client(app):  # AsyncClient avec le cookie CSRF posé (double-submit) — non requis en GET.
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
        text("DELETE FROM core.opportunities WHERE owner_user_id = :u"), {"u": str(consultant.id)}
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
async def test_dashboard_period_bound_metrics_exact() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _seed_dashboard_data(s, cabinet, client, consultant, mission)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.get(
            "/v1/cortex/dashboard",
            headers=_headers(token),
            params={"period": "2017-04"},
        )
        assert r.status_code == 200, r.text
        body = r.json()

    assert body["period"] == "2017-04"
    assert body["currency"] == "XAF"

    finance = body["finance"]
    # Deux saisies facturables approuvées de 240 min @ 45000/18000 en avril.
    assert finance["honoraires_period"] == 360000
    assert finance["cost_period"] == 144000
    assert finance["margin_period"] == 216000
    assert finance["margin_pct"] == 60
    # invoiced_period : toutes les factures issued|paid dont issued_date tombe
    # en avril 2017 (les deux, 360000 + 200000).
    assert finance["invoiced_period"] == 560000
    # collected_period : la seule facture payée dont paid_date tombe en avril.
    assert finance["collected_period"] == 200000

    production = body["production"]
    assert production["worked_hours"] == 8.0
    assert production["billable_hours"] == 8.0
    assert production["active_consultants"] == 1

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_dashboard_global_metrics_include_seeded() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        await _seed_dashboard_data(s, cabinet, client, consultant, mission)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.get(
            "/v1/cortex/dashboard",
            headers=_headers(token),
            params={"period": "2017-04"},
        )
        assert r.status_code == 200, r.text
        body = r.json()

    # Snapshots non bornés au mois : la base peut contenir d'autres données,
    # on ne peut affirmer qu'une minoration incluant nos données seedées.
    assert body["production"]["active_missions"] >= 1
    # WIP global : les 3 saisies approuvées+facturables+non facturées
    # (240 + 240 + 60 min @ 45000) = 405000, quelle que soit leur date.
    assert body["finance"]["wip"] >= 405000
    assert body["finance"]["outstanding"] >= 360000
    assert body["commercial"]["open_weighted"] >= 1_200_000

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_dashboard_invalid_period() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, _mission = await _setup_mission(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.get(
            "/v1/cortex/dashboard",
            headers=_headers(token),
            params={"period": "xxx"},
        )
    assert r.status_code == 422

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_dashboard_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/dashboard n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/dashboard") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/dashboard") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
