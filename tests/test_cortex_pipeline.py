"""Tests endpoints Cortex /v1/cortex/pipeline (CRM — pipeline commercial pondéré).

Couvre :
- POST "" : 201, étape `lead`, probabilité par défaut ; 422 si ni client_tenant_id
  ni client_name
- GET "" ?mine=true : retrouve l'opportunité du principal
- PATCH /{id} : changement d'étape sans probability applique le défaut de
  l'étape ; probability fournie explicitement l'emporte
- GET /summary (admin) : synthèse pondérée cohérente avec zolaos.crm.pipeline
- POST /{id}/convert (admin) : opportunité gagnée → Mission ; 409 si non gagnée
  ou déjà convertie
- Routes 404 en profil box (montées uniquement profil cortex)
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from zolaos.core.security import create_access_token, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import Mission, Tenant, User
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
    """JWT du consultant, porteur des deux scopes (opportunités + synthèse/conversion admin)."""
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
# Tests
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_opportunity() -> None:
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
            "/v1/cortex/pipeline",
            headers=_headers(token),
            json={
                "title": "Audit conformité RH",
                "offre": "conformite_rh",
                "client_name": "Prospect X",
                "amount_estimate": 1_000_000,
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["stage"] == "lead"
        assert body["probability"] == 10
        assert body["weighted"] == 100_000
        assert body["client_name"] == "Prospect X"
        assert body["owner_user_id"] == str(consultant_id)

        r_list = await ac.get(
            "/v1/cortex/pipeline",
            headers=_headers(token),
            params={"mine": "true"},
        )
        assert r_list.status_code == 200, r_list.text
        opps = r_list.json()
        assert any(o["id"] == body["id"] for o in opps)

        # Ni client_tenant_id ni client_name → rejet.
        r_missing = await ac.post(
            "/v1/cortex/pipeline",
            headers=_headers(token),
            json={"title": "Sans client", "offre": "conformite_rh"},
        )
        assert r_missing.status_code == 422
        assert r_missing.json()["detail"] == "need_client_tenant_or_name"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_stage_move_sets_default_probability() -> None:
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
                "title": "Fiscal OHADA",
                "offre": "fiscal_ohada",
                "client_name": "Prospect Y",
                "amount_estimate": 2_000_000,
            },
        )
        assert r_create.status_code == 201, r_create.text
        opp_id = r_create.json()["id"]

        # Avance d'étape sans fixer probability → valeur par défaut de l'étape.
        r_move = await ac.patch(
            f"/v1/cortex/pipeline/{opp_id}",
            headers=_headers(token),
            json={"stage": "proposal"},
        )
        assert r_move.status_code == 200, r_move.text
        assert r_move.json()["stage"] == "proposal"
        assert r_move.json()["probability"] == 60

        # Nouvelle étape AVEC probability explicite → la valeur fournie l'emporte.
        r_override = await ac.patch(
            f"/v1/cortex/pipeline/{opp_id}",
            headers=_headers(token),
            json={"stage": "qualified", "probability": 45},
        )
        assert r_override.status_code == 200, r_override.text
        assert r_override.json()["stage"] == "qualified"
        assert r_override.json()["probability"] == 45

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_summary_weighted() -> None:
    from zolaos.api.main import create_app

    factory = get_session_factory()
    async with factory() as s:
        cabinet, client, consultant = await _setup_cabinet_client_consultant(s)
        await s.commit()
        cabinet_id, client_id, consultant_id = cabinet.id, client.id, consultant.id

    token = _jwt_for(consultant_id)
    app = create_app()
    async with _client(app) as ac:
        opp_ids: list[str] = []
        for title, offre, amount in (
            ("Lead A", "conformite_rh", 1_000_000),
            ("Proposal B", "fiscal_ohada", 2_000_000),
            ("Won C", "cyber_audit", 500_000),
        ):
            r = await ac.post(
                "/v1/cortex/pipeline",
                headers=_headers(token),
                json={
                    "title": title,
                    "offre": offre,
                    "client_name": "Prospect Z",
                    "amount_estimate": amount,
                },
            )
            assert r.status_code == 201, r.text
            opp_ids.append(r.json()["id"])

        # Fait avancer la 2ᵉ en "proposal" (défaut 60%) et la 3ᵉ en "won" (100%).
        r_p = await ac.patch(
            f"/v1/cortex/pipeline/{opp_ids[1]}",
            headers=_headers(token),
            json={"stage": "proposal"},
        )
        assert r_p.status_code == 200, r_p.text
        r_w = await ac.patch(
            f"/v1/cortex/pipeline/{opp_ids[2]}",
            headers=_headers(token),
            json={"stage": "won"},
        )
        assert r_w.status_code == 200, r_w.text

        r_summary = await ac.get("/v1/cortex/pipeline/summary", headers=_headers(token))
        assert r_summary.status_code == 200, r_summary.text
        summary = r_summary.json()

    # lead (1_000_000@10%=100_000) + proposal (2_000_000@60%=1_200_000) = 1_300_000
    assert summary["open_amount"] == 3_000_000
    assert summary["open_weighted"] == 1_300_000
    assert summary["won_amount"] == 500_000
    assert summary["win_rate"] == 100

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_convert_won_to_mission() -> None:
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
                "title": "Audit cyber",
                "offre": "cyber_audit",
                "client_tenant_id": str(client_id),
                "amount_estimate": 3_000_000,
            },
        )
        assert r_create.status_code == 201, r_create.text
        opp_id = r_create.json()["id"]

        r_won = await ac.patch(
            f"/v1/cortex/pipeline/{opp_id}",
            headers=_headers(token),
            json={"stage": "won"},
        )
        assert r_won.status_code == 200, r_won.text
        assert r_won.json()["stage"] == "won"

        r_convert = await ac.post(
            f"/v1/cortex/pipeline/{opp_id}/convert",
            headers=_headers(token),
            json={},
        )
        assert r_convert.status_code == 200, r_convert.text
        conv = r_convert.json()
        assert conv["mission_id"]
        assert conv["opportunity"]["mission_id"] == conv["mission_id"]

        # Re-conversion : déjà convertie.
        r_again = await ac.post(
            f"/v1/cortex/pipeline/{opp_id}/convert",
            headers=_headers(token),
            json={},
        )
        assert r_again.status_code == 409
        assert r_again.json()["detail"] == "already_converted"

    async with factory() as s:
        mission = await s.scalar(select(Mission).where(Mission.cabinet_tenant_id == cabinet_id))
        assert mission is not None
        assert mission.offre == "cyber_audit"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


@pytest.mark.asyncio
async def test_convert_requires_won() -> None:
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
                "title": "Trop tôt",
                "offre": "conformite_rh",
                "client_tenant_id": str(client_id),
                "amount_estimate": 500_000,
            },
        )
        assert r_create.status_code == 201, r_create.text
        opp_id = r_create.json()["id"]
        assert r_create.json()["stage"] == "lead"

        r_convert = await ac.post(
            f"/v1/cortex/pipeline/{opp_id}/convert",
            headers=_headers(token),
            json={},
        )
        assert r_convert.status_code == 409
        assert r_convert.json()["detail"] == "must_be_won"

    async with factory() as s:
        cabinet_obj = await s.get(Tenant, cabinet_id)
        client_obj = await s.get(Tenant, client_id)
        cons_obj = await s.get(User, consultant_id)
        await _cleanup(s, cabinet_obj, client_obj, cons_obj)


def test_pipeline_routes_404_in_box_profile() -> None:
    """En profil box, /v1/cortex/pipeline n'est pas monté.

    On l'affirme par introspection de l'OpenAPI (aucune requête HTTP → pas de
    middleware rate-limit/Redis ni de boucle d'événements, donc déterministe)."""
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        paths = set(create_app().openapi()["paths"].keys())
        assert not any(p.startswith("/v1/cortex/pipeline") for p in paths)
        # ...et présent en profil cortex (contrôle de non-trivialité).
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
        cortex_paths = set(create_app().openapi()["paths"].keys())
        assert any(p.startswith("/v1/cortex/pipeline") for p in cortex_paths)
    finally:
        os.environ["ZOLAOS_PROFILE"] = "cortex"
        get_settings.cache_clear()
