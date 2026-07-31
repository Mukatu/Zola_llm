"""Tests de la relecture qualité assistée par IA d'un livrable (zolaos.ged.drafting).

Couvre :
- Fonctions pures (sans HTTP/DB) : construction de la requête de relecture
  (titre + contenu, troncature du projet au-delà d'un seuil), rubriques du
  prompt système de relecture.
- Endpoint POST /v1/cortex/ged/deliverables/{id}/review : statut renvoyé parmi
  generated/abstained/unavailable (dépend de la disponibilité réelle du LLM
  local et des embeddings — on n'affirme pas le contenu, seulement la forme),
  lecture seule (le livrable n'est JAMAIS modifié par la relecture), 422 sur
  livrable vide, 404 sur livrable inconnu, absence de la route en profil box.
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
from zolaos.db.models import Deliverable, Mission, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.ged.drafting import REVIEW_SYSTEM_PROMPT, build_review_query

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (build_review_query / REVIEW_SYSTEM_PROMPT) : aucun
# accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_build_review_query_contains_title_and_content() -> None:
    query = build_review_query("Note RH", "Le préavis est de 6 mois.")
    assert "Note RH" in query
    assert "préavis" in query


def test_build_review_query_truncates_long_content() -> None:
    content = "a" * 5000
    query = build_review_query("Note RH", content)
    assert "tronqué" in query
    assert len(query) < 5000 + 500


def test_review_prompt_has_rubrics() -> None:
    prompt = REVIEW_SYSTEM_PROMPT.lower()
    assert "bien étayé" in prompt
    assert "vérifier" in prompt
    assert "manquant" in prompt


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
# Helpers : setup cabinet/client/consultant + mission + livrable, JWT, client HTTP CSRF
# ----------------------------------------------------------------------------


async def _setup_deliverable(
    session, content: str
) -> tuple[Tenant, Tenant, User, Mission, Deliverable]:
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

    deliverable = Deliverable(
        mission_id=mission.id,
        title="Note RH",
        content=content,
        status="draft",
        version=1,
        created_by_user_id=consultant.id,
    )
    session.add(deliverable)
    await session.flush()
    return cabinet, client, consultant, mission, deliverable


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
        text("DELETE FROM core.deliverables WHERE mission_id = :m"), {"m": str(mission_id)}
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
# Tests endpoint
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_returns_valid_status_and_does_not_modify() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(
            s, "# Note\n\n## Préavis\n\nLe préavis est de 6 mois pour tous les salariés."
        )
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id, deliverable_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
            deliverable.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        # Un seul appel : la génération LLM peut prendre ~20 s si le corpus/LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            f"/v1/cortex/ged/deliverables/{deliverable_id}/review",
            headers=_headers(token),
            json={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"generated", "abstained", "unavailable"}
        if body["status"] == "generated":
            assert body["review"]
            assert isinstance(body["citations"], list)

        # La relecture est en lecture seule : le livrable ne bouge jamais.
        r_get = await ac.get(
            f"/v1/cortex/ged/deliverables/{deliverable_id}",
            headers=_headers(token),
        )
        assert r_get.status_code == 200, r_get.text
        assert r_get.json()["version"] == 1

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_review_empty_deliverable_422() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(s, "")
        await s.commit()
        cabinet_id, client_id, consultant_id, mission_id, deliverable_id = (
            cabinet.id,
            client.id,
            consultant.id,
            mission.id,
            deliverable.id,
        )

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.post(
            f"/v1/cortex/ged/deliverables/{deliverable_id}/review",
            headers=_headers(token),
            json={},
        )
    assert r.status_code == 422
    assert r.json()["detail"] == "empty_deliverable"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_review_404_missing() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(
            s, "# Note\n\nContenu."
        )
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
            f"/v1/cortex/ged/deliverables/{uuid.uuid4()}/review",
            headers=_headers(token),
            json={},
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "deliverable_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


def test_review_route_404_in_box_profile() -> None:
    """En profil box, la route de relecture qualité n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = create_app().openapi()["paths"]
        review_paths = [
            p for p in paths if p.startswith("/v1/cortex/ged/deliverables") and "/review" in p
        ]
        assert review_paths == []
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
