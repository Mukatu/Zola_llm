"""Fixtures pytest partagées."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from zolaos.api.main import create_app
from zolaos.core.settings import Settings


@pytest.fixture(autouse=True)
def _relax_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise le rate-limiter Redis en test.

    Tous les clients de test partagent l'identifiant « testclient » et le même
    compteur Redis ; le seuil 60/min de prod produirait des 429 dépendant du
    volume et du timing de la suite. Les `Settings` de test ne fixent pas ce
    champ → pydantic le lit dans l'environnement.
    """
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000000")


@pytest.fixture
def settings() -> Settings:
    """Settings de test (env minimal, fallback OFF par défaut)."""
    return Settings(
        APP_ENV="dev",
        ENABLE_EXTERNAL_FALLBACK=False,
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Client de test FastAPI."""
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
