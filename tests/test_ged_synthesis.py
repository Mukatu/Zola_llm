"""Tests de la synthèse d'entretien assistée par IA (zolaos.ged.synthesis).

Couvre :
- Fonctions pures (sans HTTP/DB) : normalisation du type d'échange, titre par
  défaut, construction du prompt (contient les notes, tronque au-delà d'un
  seuil), ensemble des types connus.
- Endpoint POST /v1/cortex/ged/deliverables/synthesis : statut renvoyé parmi
  generated/unavailable (dépend de la disponibilité réelle du LLM local — on
  n'affirme pas le contenu, seulement la forme), livrable créé (draft, v1) si
  generated et listé ensuite, 404 sur mission inconnue (avant tout appel LLM),
  422 sur notes trop courtes, absence de la route en profil box.
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
from zolaos.ged.synthesis import (
    KINDS,
    build_synthesis_prompt,
    default_title,
    normalize_kind,
)

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (normalize_kind / default_title / build_synthesis_prompt
# / KINDS) : aucun accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_normalize_kind() -> None:
    assert normalize_kind("reunion") == "reunion"
    assert normalize_kind("inconnu") == "entretien"
    assert normalize_kind(None) == "entretien"


def test_default_title() -> None:
    reunion_title = default_title("reunion")
    entretien_title = default_title("entretien")
    assert "Compte rendu" in reunion_title
    assert "Compte rendu" in entretien_title
    assert reunion_title != entretien_title


def test_build_prompt_contains_notes() -> None:
    prompt = build_synthesis_prompt("Notes: RDV avec M. X", "entretien")
    assert "Notes: RDV avec M. X" in prompt


def test_build_prompt_truncates() -> None:
    notes = "a" * 9000
    prompt = build_synthesis_prompt(notes, "entretien")
    assert len(prompt) < 9000 + 300


def test_kinds_frozen() -> None:
    for kind in ("entretien", "reunion", "atelier", "appel"):
        assert kind in KINDS


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
    # L'endpoint peut avoir créé un livrable : le purger avant la mission.
    await session.execute(
        text("DELETE FROM core.deliverables WHERE mission_id = :m"), {"m": str(mission_id)}
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
async def test_synthesis_creates_deliverable() -> None:
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
        # Un seul appel : la génération LLM peut prendre ~15-30 s si le LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            "/v1/cortex/ged/deliverables/synthesis",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "notes": (
                    "RDV avec M. Ngoma, DAF. Ils veulent un audit OHADA. Loemba "
                    "envoie la lettre de mission avant vendredi. Point telephonique "
                    "mardi."
                ),
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"generated", "unavailable"}
        if body["status"] == "generated":
            deliverable = body["deliverable"]
            assert deliverable is not None
            assert deliverable["status"] == "draft"
            assert deliverable["version"] == 1
            assert deliverable["content"]

            r_list = await ac.get(
                "/v1/cortex/ged/deliverables",
                headers=_headers(token),
                params={"mission_id": str(mission_id)},
            )
            assert r_list.status_code == 200, r_list.text
            ids = [item["id"] for item in r_list.json()]
            assert deliverable["id"] in ids
        else:
            assert body["deliverable"] is None

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_synthesis_404_missing_mission() -> None:
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
            "/v1/cortex/ged/deliverables/synthesis",
            headers=_headers(token),
            json={
                "mission_id": str(uuid.uuid4()),
                "notes": "Notes suffisamment longues pour passer la validation.",
            },
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "mission_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_synthesis_short_notes_422() -> None:
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
            "/v1/cortex/ged/deliverables/synthesis",
            headers=_headers(token),
            json={"mission_id": str(mission_id), "notes": "abcd"},
        )
    assert r.status_code == 422

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


def test_synthesis_route_404_in_box_profile() -> None:
    """En profil box, la route de synthèse d'entretien n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = create_app().openapi()["paths"]
        synthesis_paths = [p for p in paths if p.endswith("/deliverables/synthesis")]
        assert synthesis_paths == []
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
