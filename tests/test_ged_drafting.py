"""Tests de la rédaction assistée d'un livrable (zolaos.ged.drafting).

Couvre :
- Fonctions pures (sans HTTP/DB) : détection du pôle depuis l'offre, résolution
  du schéma RAG, construction de la requête de rédaction, assemblage du projet
  (corps + annexe des sources citées).
- Endpoint POST /v1/cortex/ged/deliverables/{id}/draft : statut renvoyé parmi
  generated/abstained/unavailable (dépend de la disponibilité réelle du LLM
  local et des embeddings — on n'affirme pas le contenu, seulement la forme),
  écriture conditionnée à `apply=true` (version incrémentée), 404 sur livrable
  inconnu, absence de la route en profil box.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import Deliverable, Mission, Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.ged.drafting import assemble_draft, build_draft_query, pole_from_offre, schema_for

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (pole_from_offre / schema_for / build_draft_query /
# assemble_draft) : aucun accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_pole_from_offre_mappings() -> None:
    assert pole_from_offre("conformite_rh") == "droit"
    assert pole_from_offre("audit_cyber") == "cyber"
    assert pole_from_offre("fiscal_ohada") == "erp"
    assert pole_from_offre("microfinance_aml") == "fintech"
    assert pole_from_offre("sante_publique") == "sante"


def test_pole_from_offre_defaults_to_droit_when_unknown_or_none() -> None:
    assert pole_from_offre(None) == "droit"
    assert pole_from_offre("offre_inconnue_xyz") == "droit"


def test_schema_for_droit() -> None:
    assert schema_for("droit") == ("rag_legal", ["country:cg"])


def test_schema_for_unknown_pole_uses_droit_default() -> None:
    assert schema_for("pole_inconnu") == schema_for("droit")


def test_build_draft_query_contains_title_sections_and_offre() -> None:
    query = build_draft_query("Rapport", "# R\n\n## Contexte\n\n## Constats", "conformite_rh")
    assert "Rapport" in query
    assert "Contexte" in query
    assert "Constats" in query
    assert "conformite_rh" in query


def test_assemble_draft_without_citations_has_no_sources_annex() -> None:
    body = assemble_draft("corps", [])
    assert "**Sources**" not in body
    assert "corps" in body


def test_assemble_draft_with_citations_adds_sources_annex() -> None:
    citation = SimpleNamespace(index=1, source_id="loi-x", source_uri="u", chunk_index=3)
    body = assemble_draft("corps", [citation])
    assert "**Sources**" in body
    assert "loi-x" in body


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


async def _setup_deliverable(session) -> tuple[Tenant, Tenant, User, Mission, Deliverable]:
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
        title="Rapport de conformité",
        content="# Rapport\n\n## Contexte\n\n## Constats",
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
async def test_draft_returns_valid_status() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(s)
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
        # Un seul appel : la génération LLM peut prendre ~30 s si le corpus/LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            f"/v1/cortex/ged/deliverables/{deliverable_id}/draft",
            headers=_headers(token),
            json={},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in {"generated", "abstained", "unavailable"}
    if body["status"] == "generated":
        assert body["content"]
        assert isinstance(body["citations"], list)

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_draft_apply_writes_and_bumps_version() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(s)
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
            f"/v1/cortex/ged/deliverables/{deliverable_id}/draft",
            headers=_headers(token),
            json={"apply": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()

        if body["status"] == "generated" and body["applied"]:
            r_get = await ac.get(
                f"/v1/cortex/ged/deliverables/{deliverable_id}",
                headers=_headers(token),
            )
            assert r_get.status_code == 200, r_get.text
            updated = r_get.json()
            assert updated["version"] == 2
            assert updated["content"] == body["content"]
        # Sinon (LLM/retrieval indisponible) : rien à vérifier de plus — le
        # livrable n'est pas censé avoir bougé, mais on n'en fait pas
        # dépendre le test du LLM local.

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj, mission_id)


@pytest.mark.asyncio
async def test_draft_404_missing_deliverable() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant, mission, deliverable = await _setup_deliverable(s)
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
            f"/v1/cortex/ged/deliverables/{uuid.uuid4()}/draft",
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


def test_draft_route_404_in_box_profile() -> None:
    """En profil box, la route de rédaction assistée n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert "/v1/cortex/ged/deliverables/{deliverable_id}/draft" not in paths
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
