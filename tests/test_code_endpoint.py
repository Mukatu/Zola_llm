"""Tests endpoint /v1/code/index (assistant code souverain) — profil box.

Vérifie : validation du repo_dir (400), acceptation + planification de la tâche
de fond (202), et que le tenant est **dérivé de l'identité** (jamais du body).
DB SQLite + index_repo mocké → aucun Postgres/bge-m3.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.api.auth import current_tenant
from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.db.session import get_session
from zolaos.db.store_models import StoreBase


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@asynccontextmanager
async def _client(tmp_path, tenant: str = "acme"):  # type: ignore[no-untyped-def]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/code.db")
    async with engine.begin() as conn:
        await conn.run_sync(StoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():  # type: ignore[no-untyped-def]
        async with factory() as s:
            yield s

    app = create_app(settings=_settings())
    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[current_tenant] = lambda: tenant
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        await engine.dispose()


async def test_index_rejects_missing_repo_dir(tmp_path) -> None:  # type: ignore[no-untyped-def]
    async with _client(tmp_path) as ac:
        r = await ac.post("/v1/code/index", json={"repo_dir": str(tmp_path / "nope")})
        assert r.status_code == 400
        assert r.json()["detail"] == "repo_dir introuvable sur la box"


async def test_index_accepts_and_derives_tenant(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: dict[str, object] = {}

    async def _fake_index_repo(repo_dir, tenant, *, since=None, reindex=False, **kw):  # type: ignore[no-untyped-def]
        calls["tenant"] = tenant
        calls["repo_dir"] = str(repo_dir)
        calls["since"] = since
        return {"indexed": 1, "skipped": 0, "deleted": 0, "chunks": 3}

    # L'endpoint importe index_repo paresseusement depuis scripts.index_codebase.
    monkeypatch.setattr("scripts.index_codebase.index_repo", _fake_index_repo)

    repo = tmp_path / "repo"
    repo.mkdir()
    async with _client(tmp_path, tenant="acme") as ac:
        r = await ac.post("/v1/code/index", json={"repo_dir": str(repo), "since": "HEAD~5"})
        assert r.status_code == 202
        body = r.json()
        assert body["accepted"] is True
        assert body["tenant"] == "acme"  # dérivé de l'identité, PAS du body

    # La tâche de fond a bien tourné, avec le tenant authentifié et la bonne ref.
    assert calls.get("tenant") == "acme"
    assert calls.get("since") == "HEAD~5"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
