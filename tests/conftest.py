"""Fixtures pytest partagées."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from zolaos.api.main import create_app
from zolaos.core.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """Settings de test (env minimal, fallback OFF par défaut)."""
    return Settings(
        APP_ENV="dev",
        ENABLE_EXTERNAL_FALLBACK=False,
        POSTGRES_PASSWORD_APP="x",  # noqa: S106  (test only)
        POSTGRES_PASSWORD_MIGRATIONS="x",  # noqa: S106
        JWT_SECRET="x" * 32,  # noqa: S106
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Client de test FastAPI."""
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
