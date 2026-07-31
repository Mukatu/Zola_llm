"""Tests du mémo réglementaire (question → note ancrée, enregistrée en livrable).

Couvre :
- Fonctions pures (sans HTTP/DB) : construction de la requête de mémo (contient la
  question), rubriques du prompt système du mémo, titre par défaut dérivé de la
  question (`_memo_title`).
- Endpoint POST /v1/cortex/ged/deliverables/memo : statut renvoyé parmi
  generated/abstained/unavailable (dépend de la disponibilité réelle du LLM local
  et des embeddings — on n'affirme pas le contenu, seulement la forme) ; un
  livrable est CRÉÉ (draft, version 1) uniquement si `generated` ; 404 sur mission
  inconnue ; absence de la route en profil box.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.api.v1.cortex_ged import _memo_title
from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import Mission, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.ged.drafting import MEMO_SYSTEM_PROMPT, build_memo_query

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (build_memo_query / MEMO_SYSTEM_PROMPT / _memo_title) :
# aucun accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_build_memo_query_contains_question() -> None:
    query = build_memo_query("Quelles sont les obligations de préavis pour un cadre en CDI ?")
    assert "Quelles sont les obligations de préavis pour un cadre en CDI ?" in query


def test_memo_prompt_has_rubrics() -> None:
    prompt = MEMO_SYSTEM_PROMPT.lower()
    assert "réponse" in prompt
    assert "fondement" in prompt
    assert "vérifier" in prompt


def test_memo_title_truncates() -> None:
    short = "Quel est le préavis ?"
    title = _memo_title(short)
    assert title.startswith("Note : ")
    assert short in title

    long_question = "a" * 200
    long_title = _memo_title(long_question)
    assert "…" in long_title


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
# Helpers : setup cabinet/client/consultant + mission (pas de livrable — c'est
# l'endpoint qui le crée), JWT, client HTTP CSRF
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
async def test_memo_returns_valid_status_and_may_create() -> None:
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
        # Un seul appel : la génération LLM peut prendre ~20-30 s si le corpus/LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            "/v1/cortex/ged/deliverables/memo",
            headers=_headers(token),
            json={
                "mission_id": str(mission_id),
                "question": "Quelles sont les obligations de préavis pour un cadre en CDI ?",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"generated", "abstained", "unavailable"}

        r_list = await ac.get(
            "/v1/cortex/ged/deliverables",
            params={"mission_id": str(mission_id)},
            headers=_headers(token),
        )
        assert r_list.status_code == 200, r_list.text
        deliverables = r_list.json()

        if body["status"] == "generated":
            assert body["deliverable"] is not None
            assert body["deliverable"]["status"] == "draft"
            assert body["deliverable"]["version"] == 1
            assert body["deliverable"]["content"]
            assert deliverables
        else:
            assert body["deliverable"] is None
            assert deliverables == []

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_memo_404_missing_mission() -> None:
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
            "/v1/cortex/ged/deliverables/memo",
            headers=_headers(token),
            json={
                "mission_id": str(uuid.uuid4()),
                "question": "Quel est le délai de préavis ?",
            },
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "mission_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


def test_memo_route_404_in_box_profile() -> None:
    """En profil box, la route de mémo réglementaire n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = create_app().openapi()["paths"]
        memo_paths = [
            p
            for p in paths
            if p.startswith("/v1/cortex/ged/deliverables") and p.endswith("/memo")
        ]
        assert memo_paths == []
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
