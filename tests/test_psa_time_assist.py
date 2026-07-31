"""Tests de la saisie de temps assistée par IA (zolaos.psa.time_assist).

Couvre :
- Fonctions pures (sans réseau/DB) : construction du prompt (récit + lundi de
  référence + missions), parsing robuste de la sortie JSON du LLM (bornage des
  durées à 24 h, rejet des entrées invalides, anti-hallucination sur
  mission_id, plafond de 30 suggestions).
- Endpoint POST /v1/cortex/psa/time-entries/assist : statut renvoyé parmi
  suggested/unavailable, **ne crée rien** (le consultant valide chaque ligne),
  422 sur récit trop court, absence de la route en profil box.
"""

from __future__ import annotations

import json
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
from zolaos.psa.time_assist import _parse_entries, build_prompt

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (build_prompt / _parse_entries) : aucun accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_build_prompt_contains_narrative_and_missions() -> None:
    missions = [{"id": "m-1", "label": "audit_conformite — ACME"}]
    prompt = build_prompt("Lundi 3h sur l'audit ACME.", date(2026, 7, 27), missions)
    assert "Lundi 3h sur l'audit ACME." in prompt
    assert date(2026, 7, 27).isoformat() in prompt
    assert "audit_conformite — ACME" in prompt


def test_parse_valid_entries() -> None:
    mission_id = str(uuid.uuid4())
    raw = json.dumps(
        {
            "entries": [
                {
                    "date": "2026-07-27",
                    "hours": 3,
                    "activity": "revue",
                    "mission_id": mission_id,
                    "billable": True,
                }
            ]
        }
    )
    labels = {mission_id: "audit_conformite — ACME"}
    out = _parse_entries(raw, {mission_id}, labels)
    assert len(out) == 1
    entry = out[0]
    assert entry.minutes == 180
    assert entry.entry_date == "2026-07-27"
    assert entry.mission_id == mission_id
    assert entry.mission_label == "audit_conformite — ACME"


def test_parse_clamps_and_rejects() -> None:
    raw = json.dumps(
        {
            "entries": [
                {"hours": 100, "activity": "trop long"},
                {"hours": 0, "activity": "zero"},
                {"activity": "sans duree"},
                "pas-un-dict",
            ]
        }
    )
    out = _parse_entries(raw, set(), {})
    assert len(out) == 1
    assert out[0].minutes == 24 * 60


def test_parse_rejects_unknown_mission_id() -> None:
    raw = json.dumps(
        {"entries": [{"hours": 1, "activity": "x", "mission_id": "id-invente"}]}
    )
    out = _parse_entries(raw, {"id-valide"}, {"id-valide": "Mission valide"})
    assert len(out) == 1
    assert out[0].mission_id is None
    assert out[0].mission_label is None


def test_parse_invalid_date_to_none() -> None:
    raw = json.dumps({"entries": [{"date": "pas une date", "hours": 2, "activity": "x"}]})
    out = _parse_entries(raw, set(), {})
    assert len(out) == 1
    assert out[0].entry_date is None
    assert out[0].minutes == 120


def test_parse_caps_at_30() -> None:
    entries = [{"hours": 1, "activity": f"tache-{i}"} for i in range(40)]
    raw = json.dumps({"entries": entries})
    out = _parse_entries(raw, set(), {})
    assert len(out) <= 30


def test_parse_non_json_raises() -> None:
    with pytest.raises(Exception):
        _parse_entries("pas du json", set(), {})


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
    # Défensif : l'endpoint assist ne crée rien, mais on nettoie quand même
    # au cas où pour ne rien laisser derrière ce test.
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
# Tests endpoint
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assist_returns_valid_status() -> None:
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
        # Un seul appel : la génération LLM peut prendre ~10-25 s si le LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            "/v1/cortex/psa/time-entries/assist",
            headers=_headers(token),
            json={"narrative": "Lundi 3h sur l'audit ACME, mardi 2h de cadrage fiscal."},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"suggested", "unavailable"}
        assert isinstance(body["suggestions"], list)
        for suggestion in body["suggestions"]:
            assert suggestion["minutes"] > 0
            assert suggestion["hours"] > 0

        # Ne crée RIEN : aucune feuille de temps n'apparaît pour ce consultant.
        r_list = await ac.get(
            "/v1/cortex/psa/time-entries",
            headers=_headers(token),
            params={"mission_id": str(mission_id)},
        )
        assert r_list.status_code == 200, r_list.text
        assert r_list.json() == []

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_assist_short_narrative_422() -> None:
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
            "/v1/cortex/psa/time-entries/assist",
            headers=_headers(token),
            json={"narrative": "ok"},
        )
    assert r.status_code == 422

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


def test_assist_route_404_in_box_profile() -> None:
    """En profil box, la saisie de temps assistée n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = create_app().openapi()["paths"]
        assist_paths = [p for p in paths if p.endswith("/time-entries/assist")]
        assert assist_paths == []
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
