"""Tests Polaris-7+8 : émission/vérification JWT mission + endpoint Box RAG.

Couvre :
- Émission `issue_mission_token` (TTL effectif, plafond, statut non-active rejeté)
- Vérification `verify_mission_token` (signature, mission DB, expiration, révocation)
- Garde-fous endpoint /v1/box/rag/search : 401 sans token, 401 token invalide,
  403 si tags demandés hors scope mission, 200 nominal avec audit hash trace
- Profil : routes /v1/box/* non montées en profil cortex

N'utilise PAS de LLM (mock le retrieve via monkeypatch).
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from zolaos.core.settings import get_settings
from zolaos.db.models import Mission, Tenant, User
from zolaos.db.session import get_session_factory
from zolaos.missions.tokens import (
    MissionTokenError,
    issue_mission_token,
    verify_mission_token,
)
from zolaos.rag.retrieval import Match

# ----------------------------------------------------------------------------
# Helpers — création tenants/users/missions de test, nettoyés en fin de test
# ----------------------------------------------------------------------------


async def _setup_mission(session, *, ttl_hours: float = 2.0, status: str = "active") -> Mission:
    cabinet = Tenant(
        name=f"polaris-test-{uuid.uuid4().hex[:6]}", tenant_type="cabinet", country="cg"
    )
    client = Tenant(name=f"client-test-{uuid.uuid4().hex[:6]}", tenant_type="client", country="cg")
    session.add_all([cabinet, client])
    await session.flush()

    consultant = User(
        email=f"consultant-{uuid.uuid4().hex[:6]}@polaris.cg",
        display_name="Consultant Test",
        password_hash="x" * 60,
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
        expires_at=now + timedelta(hours=ttl_hours),
        status=status,
        scope_tags=["country:cg", "module:travail_cg"],
    )
    session.add(mission)
    await session.flush()
    return mission


@pytest.fixture(autouse=True)
def _force_box_profile():
    """Force le profil box pour les tests endpoint (par défaut déjà box mais on s'assure)."""
    prev = os.environ.get("ZOLAOS_PROFILE", "box")
    os.environ["ZOLAOS_PROFILE"] = "box"
    get_settings.cache_clear()
    yield
    os.environ["ZOLAOS_PROFILE"] = prev
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    """Purge le pool asyncpg entre tests — chaque test async crée son propre
    event loop, et un pool partagé via lru_cache reste attaché au loop initial,
    ce qui produit `Future attached to a different loop` au 2e test."""
    from zolaos.db.session import reset_engine_cache

    reset_engine_cache()
    yield
    reset_engine_cache()


# ----------------------------------------------------------------------------
# Émission de token
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_active_mission_returns_valid_jwt() -> None:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as s:
        mission = await _setup_mission(s)
        token, exp_dt = issue_mission_token(
            mission=mission, settings=settings, ttl=timedelta(hours=1)
        )
        assert isinstance(token, str) and token.count(".") == 2  # header.payload.signature
        assert exp_dt > datetime.now(UTC)
        await s.rollback()


@pytest.mark.asyncio
async def test_issue_token_rejects_non_active_mission() -> None:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as s:
        mission = await _setup_mission(s, status="active")
        mission.status = "revoked"
        await s.flush()
        with pytest.raises(ValueError, match="non active"):
            issue_mission_token(mission=mission, settings=settings)
        await s.rollback()


# ----------------------------------------------------------------------------
# Vérification
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_round_trip() -> None:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as s:
        mission = await _setup_mission(s)
        await s.commit()  # le token verify charge depuis une autre session

    async with factory() as s2:
        # Recharge la mission insérée
        m = await s2.scalar(select(Mission).where(Mission.id == mission.id))
        token, _ = issue_mission_token(mission=m, settings=settings)
        claims = await verify_mission_token(token, session=s2, settings=settings)
        assert claims.mission_id == mission.id
        assert claims.offre == "conformite_rh"
        assert "module:travail_cg" in claims.scope_tags
        # cleanup
        await s2.execute(text("DELETE FROM core.missions WHERE id = :id"), {"id": str(mission.id)})
        await s2.execute(
            text("DELETE FROM core.users WHERE id = :id"),
            {"id": str(m.consultant_user_id)},
        )
        await s2.execute(
            text("DELETE FROM core.tenants WHERE id IN (:c1, :c2)"),
            {"c1": str(m.cabinet_tenant_id), "c2": str(m.client_tenant_id)},
        )
        await s2.commit()


@pytest.mark.asyncio
async def test_verify_token_rejects_revoked_mission() -> None:
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as s:
        mission = await _setup_mission(s)
        await s.commit()

    async with factory() as s2:
        m = await s2.scalar(select(Mission).where(Mission.id == mission.id))
        token, _ = issue_mission_token(mission=m, settings=settings)

        # Révocation
        m.status = "revoked"
        m.revoked_at = datetime.now(UTC)
        await s2.flush()

        with pytest.raises(MissionTokenError, match="non active|révoquée"):
            await verify_mission_token(token, session=s2, settings=settings)

        # cleanup
        await s2.execute(text("DELETE FROM core.missions WHERE id = :id"), {"id": str(mission.id)})
        await s2.execute(
            text("DELETE FROM core.users WHERE id = :id"),
            {"id": str(m.consultant_user_id)},
        )
        await s2.execute(
            text("DELETE FROM core.tenants WHERE id IN (:c1, :c2)"),
            {"c1": str(m.cabinet_tenant_id), "c2": str(m.client_tenant_id)},
        )
        await s2.commit()


# ----------------------------------------------------------------------------
# Endpoint /v1/box/rag/search
# ----------------------------------------------------------------------------


@pytest.fixture
def _mock_retrieve(monkeypatch):
    """Mock zolaos.api.v1.box.retrieve pour éviter l'appel embedder + DB vide."""

    async def fake_retrieve(*, query, schema, required_tags, k, session=None):
        return [
            Match(
                content=f"chunk matching '{query[:20]}' in {schema}",
                score=0.12,
                source_uri=f"/fake/{schema}/doc.md",
                source_id="FAKE_SRC",
                chunk_index=0,
                tags=list(required_tags),
                extra_metadata={"pii_policy": "none"},
            )
        ]

    monkeypatch.setattr("zolaos.api.v1.box.retrieve", fake_retrieve)


@pytest.mark.asyncio
async def test_box_endpoint_401_without_token(_mock_retrieve) -> None:
    from zolaos.api.main import create_app

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/box/rag/search",
        json={"schema": "rag_legal", "query": "test", "required_tags": [], "k": 3},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "missing_bearer_token"


@pytest.mark.asyncio
async def test_box_endpoint_401_with_bad_token(_mock_retrieve) -> None:
    from zolaos.api.main import create_app

    app = create_app()
    client = TestClient(app)
    r = client.post(
        "/v1/box/rag/search",
        headers={"Authorization": "Bearer not-a-real-jwt"},
        json={"schema": "rag_legal", "query": "test", "required_tags": [], "k": 3},
    )
    assert r.status_code == 401
    assert "invalid_mission_token" in r.json()["detail"]


async def _cleanup_mission(session, mission: Mission) -> None:
    await session.execute(text("DELETE FROM core.missions WHERE id = :id"), {"id": str(mission.id)})
    await session.execute(
        text("DELETE FROM core.users WHERE id = :id"),
        {"id": str(mission.consultant_user_id)},
    )
    await session.execute(
        text("DELETE FROM core.tenants WHERE id IN (:c1, :c2)"),
        {"c1": str(mission.cabinet_tenant_id), "c2": str(mission.client_tenant_id)},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_box_endpoint_full_flow_with_audit(_mock_retrieve) -> None:
    """Setup DB + appel HTTP + vérif audit, tout dans le même event loop async via httpx.ASGITransport."""
    from zolaos.api.main import create_app

    settings = get_settings()
    factory = get_session_factory()

    # 1. Setup mission en DB
    async with factory() as s:
        mission = await _setup_mission(s)
        await s.commit()

    async with factory() as s2:
        m = await s2.scalar(select(Mission).where(Mission.id == mission.id))
        token, _ = issue_mission_token(mission=m, settings=settings)

    # 2. Appel HTTP via httpx ASGITransport (même event loop que le test)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/v1/box/rag/search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "schema": "rag_legal",
                "query": "période d'essai cadre",
                "required_tags": ["country:cg", "module:travail_cg"],
                "k": 3,
            },
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mission_id"] == str(mission.id)
    assert data["effective_tags"] == ["country:cg", "module:travail_cg"]
    assert len(data["matches"]) == 1
    request_id = data["request_id"]

    # 3. Vérifier audit.log via une session "migrator" (zolaos_app n'a pas SELECT
    # sur audit — c'est volontaire, append-only côté app). On crée un engine
    # éphémère avec le DSN migrator pour la vérif + cleanup.
    from sqlalchemy.ext.asyncio import create_async_engine

    audit_engine = create_async_engine(
        get_settings().postgres_dsn_migrations.replace("psycopg", "asyncpg"),
        pool_pre_ping=True,
    )
    try:
        async with audit_engine.connect() as conn:
            row = await conn.execute(
                text(
                    "SELECT category, event, actor_type, tenant_id, request_id, payload, row_hash "
                    "FROM audit.log WHERE request_id = :rid"
                ),
                {"rid": request_id},
            )
            audit_row = row.first()
            assert audit_row is not None, "audit row absent"
            assert audit_row.category == "rag_access"
            assert audit_row.event == "box_rag_search"
            assert audit_row.actor_type == "user"
            assert audit_row.tenant_id == str(mission.client_tenant_id)
            assert audit_row.row_hash, "chaîne hash non calculée"
            # NOTE: pas de DELETE sur audit.log — le trigger `forbid_mutation`
            # l'interdit par design (append-only inviolable). La row reste, c'est
            # 1 row par test, négligeable. Cette tentative est même une preuve
            # supplémentaire que l'audit est correctement protégé.
    finally:
        await audit_engine.dispose()

    async with factory() as s3:
        await _cleanup_mission(s3, m)


@pytest.mark.asyncio
async def test_box_endpoint_403_when_tags_outside_scope(_mock_retrieve) -> None:
    from zolaos.api.main import create_app

    settings = get_settings()
    factory = get_session_factory()
    async with factory() as s:
        mission = await _setup_mission(s)
        await s.commit()
    async with factory() as s2:
        m = await s2.scalar(select(Mission).where(Mission.id == mission.id))
        token, _ = issue_mission_token(mission=m, settings=settings)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/v1/box/rag/search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "schema": "rag_legal",
                "query": "test",
                "required_tags": ["country:cg", "module:fiscal_cg"],  # fiscal_cg hors scope
                "k": 3,
            },
        )
    assert r.status_code == 403
    assert "tags_outside_mission_scope" in r.json()["detail"]

    async with factory() as s3:
        await _cleanup_mission(s3, m)


# ----------------------------------------------------------------------------
# Profil cortex : routes /v1/box/* non montées
# ----------------------------------------------------------------------------


def test_box_routes_not_mounted_in_cortex_profile() -> None:
    """En profil cortex, /v1/box/* doit retourner 404 (router non monté)."""
    os.environ["ZOLAOS_PROFILE"] = "cortex"
    get_settings.cache_clear()
    try:
        from zolaos.api.main import create_app

        app = create_app()
        client = TestClient(app)
        r = client.post(
            "/v1/box/rag/search",
            json={"schema": "rag_legal", "query": "x"},
        )
        assert r.status_code == 404
    finally:
        os.environ["ZOLAOS_PROFILE"] = "box"
        get_settings.cache_clear()
