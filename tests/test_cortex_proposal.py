"""Tests de la proposition commerciale assistée par IA (pipeline CRM Cortex).

Couvre :
- Fonctions pures (zolaos.ged.drafting) : construction de la requête de
  proposition (titre/offre/client + garde-fou « ne chiffre aucun honoraire »),
  prompt système interdisant tout montant.
- Endpoint POST /v1/cortex/pipeline/{id}/proposal/draft : statut renvoyé parmi
  generated/abstained/unavailable (dépend de la disponibilité réelle du LLM
  local et des embeddings — on n'affirme pas le contenu, seulement la forme),
  écriture dans l'opportunité conditionnée à `apply=true`, 404 sur opportunité
  inconnue, absence de la route en profil box. L'édition manuelle du champ
  `proposal` via PATCH ne dépend d'aucune génération IA.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import Tenant, User
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.ged.drafting import PROPOSAL_SYSTEM_PROMPT, build_proposal_query

_CSRF = "test-csrf-token"

# ----------------------------------------------------------------------------
# Tests unitaires purs (build_proposal_query / PROPOSAL_SYSTEM_PROMPT) : aucun
# accès réseau ni DB.
# ----------------------------------------------------------------------------


def test_build_proposal_query_contains_context() -> None:
    query = build_proposal_query("Audit RH", "conformite_rh", "ACME")
    assert "Audit RH" in query
    assert "conformite_rh" in query
    assert "ACME" in query
    assert "Ne chiffre aucun honoraire" in query


def test_proposal_prompt_forbids_pricing() -> None:
    assert "AUCUN MONTANT" in PROPOSAL_SYSTEM_PROMPT


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
# Helpers : setup cabinet/client/consultant, JWT, client HTTP CSRF
# ----------------------------------------------------------------------------


async def _setup_cabinet_client_consultant(session) -> tuple[Tenant, Tenant, User]:
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
    return cabinet, client, consultant


def _jwt_for(user_id: uuid.UUID) -> str:
    """JWT du consultant, porteur des deux scopes (opportunités + accès admin)."""
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
        text("DELETE FROM core.opportunities WHERE owner_user_id = :u"),
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
async def test_proposal_draft_returns_valid_status() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant = await _setup_cabinet_client_consultant(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_create = await ac.post(
            "/v1/cortex/pipeline",
            headers=_headers(token),
            json={
                "title": "Audit conformité",
                "offre": "conformite_rh",
                "client_name": "ACME",
            },
        )
        assert r_create.status_code == 201, r_create.text
        opp_id = r_create.json()["id"]

        # Un seul appel : la génération LLM peut prendre ~30 s si le corpus/LLM
        # local est disponible — c'est normal, on n'en fait qu'un.
        r = await ac.post(
            f"/v1/cortex/pipeline/{opp_id}/proposal/draft",
            headers=_headers(token),
            json={"apply": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] in {"generated", "abstained", "unavailable"}

        if body["status"] == "generated" and body["applied"]:
            r_list = await ac.get(
                "/v1/cortex/pipeline",
                headers=_headers(token),
                params={"mine": "true"},
            )
            assert r_list.status_code == 200, r_list.text
            opp_out = next(o for o in r_list.json() if o["id"] == opp_id)
            assert opp_out["proposal"]
        # Sinon (LLM/retrieval indisponible ou abstention) : rien de plus à
        # vérifier — on ne fait pas dépendre le test du LLM local.

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_proposal_manual_edit() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant = await _setup_cabinet_client_consultant(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r_create = await ac.post(
            "/v1/cortex/pipeline",
            headers=_headers(token),
            json={
                "title": "Audit conformité",
                "offre": "conformite_rh",
                "client_name": "ACME",
            },
        )
        assert r_create.status_code == 201, r_create.text
        opp_id = r_create.json()["id"]

        r_patch = await ac.patch(
            f"/v1/cortex/pipeline/{opp_id}",
            headers=_headers(token),
            json={"proposal": "Ma proposition manuelle"},
        )
        assert r_patch.status_code == 200, r_patch.text
        assert r_patch.json()["proposal"] == "Ma proposition manuelle"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_proposal_draft_404_missing() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant = await _setup_cabinet_client_consultant(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        r = await ac.post(
            f"/v1/cortex/pipeline/{uuid.uuid4()}/proposal/draft",
            headers=_headers(token),
            json={},
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "opportunity_not_found"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_proposal_route_404_in_box_profile() -> None:
    """En profil box, la rédaction assistée de proposition n'est pas montée.

    On l'affirme par introspection de l'OpenAPI (pas de requête HTTP réelle →
    déterministe, sans dépendance à Redis/Docker)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(
            p.startswith("/v1/cortex/pipeline") and "/proposal/draft" in p for p in paths
        )
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
