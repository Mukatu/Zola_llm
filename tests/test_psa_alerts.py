"""Tests des alertes marge & sous-facturation (zolaos.psa.alerts) — PSA.

Couvre :
- Bloc A — fonctions pures (sans HTTP/DB) : `scan_mission`/`scan_alerts` (seuils
  par défaut et personnalisés, priorité marge négative > marge faible, tri par
  sévérité puis impact), `build_narration_prompt`, court-circuit `empty` de
  `narrate_alerts` sans alerte (aucun appel LLM).
- Bloc B — endpoints GET /v1/cortex/psa/alerts et POST /v1/cortex/psa/alerts/brief
  (réservés admin) : alerte de sous-facturation déterministe via une saisie de
  temps insérée directement, statut de la note de pilotage, absence de la route
  en profil box.
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
from zolaos.psa.alerts import (
    MARGE_FAIBLE,
    MARGE_NEGATIVE,
    SOUS_FACTURATION,
    Thresholds,
    build_narration_prompt,
    narrate_alerts,
    scan_alerts,
    scan_mission,
)

_CSRF = "test-csrf-token"


# ----------------------------------------------------------------------------
# Bloc A — tests purs (aucun réseau/DB)
# ----------------------------------------------------------------------------


def test_marge_negative_high() -> None:
    econ = {"honoraires": 800_000, "cost": 950_000, "margin": -150_000, "margin_pct": -19}
    alerts = scan_mission(
        mission_id="m1", offre="audit", econ=econ, unbilled_wip=0, thresholds=Thresholds()
    )
    assert len(alerts) == 1
    assert alerts[0].type == MARGE_NEGATIVE
    assert alerts[0].severity == "high"
    assert alerts[0].impact == 150_000


def test_marge_faible_medium() -> None:
    econ = {"honoraires": 1_200_000, "cost": 1_050_000, "margin": 150_000, "margin_pct": 13}
    alerts = scan_mission(
        mission_id="m2", offre="conformite", econ=econ, unbilled_wip=0, thresholds=Thresholds()
    )
    assert len(alerts) == 1
    assert alerts[0].type == MARGE_FAIBLE
    assert alerts[0].severity == "medium"


def test_marge_ok_no_alert() -> None:
    econ = {"honoraires": 1_200_000, "cost": 480_000, "margin": 720_000, "margin_pct": 60}
    alerts = scan_mission(
        mission_id="m3", offre="audit", econ=econ, unbilled_wip=0, thresholds=Thresholds()
    )
    assert alerts == []


def test_small_mission_suppressed() -> None:
    econ = {"honoraires": 50_000, "cost": 45_000, "margin": 5_000, "margin_pct": 10}
    alerts = scan_mission(
        mission_id="m4", offre="petite_mission", econ=econ, unbilled_wip=0, thresholds=Thresholds()
    )
    assert not any(a.type == MARGE_FAIBLE for a in alerts)
    assert alerts == []


def test_sous_facturation_threshold() -> None:
    econ = {"honoraires": 1_000_000, "cost": 400_000, "margin": 600_000, "margin_pct": 60}

    below = scan_mission(
        mission_id="m5", offre="audit", econ=econ, unbilled_wip=300_000, thresholds=Thresholds()
    )
    assert below == []

    medium = scan_mission(
        mission_id="m5", offre="audit", econ=econ, unbilled_wip=600_000, thresholds=Thresholds()
    )
    assert len(medium) == 1
    assert medium[0].type == SOUS_FACTURATION
    assert medium[0].severity == "medium"

    high = scan_mission(
        mission_id="m5", offre="audit", econ=econ, unbilled_wip=1_400_000, thresholds=Thresholds()
    )
    assert len(high) == 1
    assert high[0].type == SOUS_FACTURATION
    assert high[0].severity == "high"


def test_negative_takes_priority_over_faible() -> None:
    econ = {"honoraires": 800_000, "cost": 950_000, "margin": -150_000, "margin_pct": -19}
    alerts = scan_mission(
        mission_id="m6",
        offre="audit",
        econ=econ,
        unbilled_wip=1_400_000,
        thresholds=Thresholds(),
    )
    types = [a.type for a in alerts]
    assert types.count(MARGE_NEGATIVE) == 1
    assert MARGE_FAIBLE not in types
    assert SOUS_FACTURATION in types


def test_scan_sorts_by_severity_then_impact() -> None:
    missions = [
        {
            "mission_id": "low-impact-high",
            "offre": "a",
            "econ": {"honoraires": 500_000, "cost": 600_000, "margin": -100_000, "margin_pct": -20},
            "unbilled_wip": 0,
        },
        {
            "mission_id": "big-impact-high",
            "offre": "b",
            "econ": {
                "honoraires": 2_000_000,
                "cost": 3_000_000,
                "margin": -1_000_000,
                "margin_pct": -50,
            },
            "unbilled_wip": 0,
        },
        {
            "mission_id": "medium-faible",
            "offre": "c",
            "econ": {
                "honoraires": 1_200_000,
                "cost": 1_050_000,
                "margin": 150_000,
                "margin_pct": 13,
            },
            "unbilled_wip": 0,
        },
    ]
    alerts = scan_alerts(missions)
    severities = [a.severity for a in alerts]
    # Tous les "high" précèdent tous les "medium"/"low".
    assert severities.index("medium") > max(
        (i for i, s in enumerate(severities) if s == "high"), default=-1
    )
    high_alerts = [a for a in alerts if a.severity == "high"]
    assert len(high_alerts) == 2
    assert high_alerts[0].impact >= high_alerts[1].impact
    assert high_alerts[0].mission_id == "big-impact-high"


def test_custom_thresholds() -> None:
    custom = Thresholds(margin_low_pct=30, wip_alert_xaf=100_000, min_honoraires_xaf=0)

    # Une marge de 25% n'aurait pas déclenché avec le seuil par défaut (20%)
    # mais devient "faible" avec le seuil personnalisé (30%).
    econ_25 = {"honoraires": 1_000_000, "cost": 750_000, "margin": 250_000, "margin_pct": 25}
    default_alerts = scan_mission(
        mission_id="m7", offre="a", econ=econ_25, unbilled_wip=0, thresholds=Thresholds()
    )
    assert default_alerts == []
    custom_alerts = scan_mission(
        mission_id="m7", offre="a", econ=econ_25, unbilled_wip=0, thresholds=custom
    )
    assert len(custom_alerts) == 1
    assert custom_alerts[0].type == MARGE_FAIBLE

    # Petite mission (< 100 000 XAF) normalement supprimée : ne l'est plus avec
    # min_honoraires_xaf=0.
    econ_small = {"honoraires": 50_000, "cost": 45_000, "margin": 5_000, "margin_pct": 10}
    small_default = scan_mission(
        mission_id="m8", offre="b", econ=econ_small, unbilled_wip=0, thresholds=Thresholds()
    )
    assert small_default == []
    small_custom = scan_mission(
        mission_id="m8", offre="b", econ=econ_small, unbilled_wip=0, thresholds=custom
    )
    assert len(small_custom) == 1
    assert small_custom[0].type == MARGE_FAIBLE


def test_build_narration_prompt_contains_numbers() -> None:
    econ = {"honoraires": 800_000, "cost": 950_000, "margin": -150_000, "margin_pct": -19}
    alerts = scan_mission(
        mission_id="m9", offre="audit_rh", econ=econ, unbilled_wip=0, thresholds=Thresholds()
    )
    prompt = build_narration_prompt(alerts)
    assert "audit_rh" in prompt
    assert "-150000" in prompt or "-150 000" in prompt or str(-150_000) in prompt
    assert "800000" in prompt or str(800_000) in prompt


@pytest.mark.asyncio
async def test_narrate_empty_no_llm() -> None:
    # Aucune alerte : court-circuit avant tout appel LLM (get_settings() suffit,
    # même si le LLM local n'est pas disponible dans l'environnement de test).
    outcome = await narrate_alerts(get_settings(), [])
    assert outcome.status == "empty"
    assert outcome.brief != ""


# ----------------------------------------------------------------------------
# Bloc B — fixtures profil + reset DB engine (calqué sur test_ged_review.py)
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
# Helpers : setup cabinet/client/consultant + mission (+ saisie de temps), JWT,
# client HTTP CSRF.
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
        offre="audit_marge",
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


async def _cleanup(
    session, cabinet: Tenant, client: Tenant, consultant: User, mission_id: uuid.UUID
) -> None:
    await session.execute(
        text("DELETE FROM core.time_entries WHERE mission_id = :m"), {"m": str(mission_id)}
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
# Tests endpoints
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alerts_endpoint_lists_own_mission() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission = await _setup_mission(s)
        # Saisie déterministe : honoraires 4 500 000, coût 1 800 000 (marge forte,
        # positive) mais TOUT approuvé/facturable/sans facture → sous-facturation
        # "high" (unbilled_wip 4 500 000 >= 2 x seuil par défaut 500 000).
        entry = TimeEntry(
            consultant_user_id=consultant.id,
            mission_id=mission.id,
            entry_date=date.today(),
            minutes=6000,
            billable=True,
            activity="audit",
            status="approved",
            bill_rate=45_000,
            cost_rate=18_000,
            invoice_id=None,
        )
        s.add(entry)
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
        r = await ac.get("/v1/cortex/psa/alerts", headers=_headers(token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "thresholds" in body
        assert set(body["thresholds"]) == {
            "margin_low_pct",
            "wip_alert_xaf",
            "min_honoraires_xaf",
        }
        mine = [a for a in body["alerts"] if a["mission_id"] == str(mission_id)]
        assert any(a["type"] == "sous_facturation" for a in mine)

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_alerts_brief_status() -> None:
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
        # Un seul appel : la note de pilotage peut prendre ~10-25 s si le LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            "/v1/cortex/psa/alerts/brief",
            headers=_headers(token),
            json={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"generated", "unavailable", "empty"}
        assert isinstance(body["count"], int)

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


def test_alerts_route_404_in_box_profile() -> None:
    """En profil box, les routes d'alertes PSA ne sont pas montées.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = create_app().openapi()["paths"]
        alert_paths = [p for p in paths if "/psa/alerts" in p]
        assert alert_paths == []
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
