"""Fixtures pytest partagées."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from zolaos.api import auth as _auth
from zolaos.api import main as _main
from zolaos.core.settings import Settings

# --- Authentification du plan de données en test -----------------------------
# Le plan de données de la box exige désormais une identité (`require_box_auth`).
# Pour ne pas ré-outiller les ~34 harnesses (`_client`), on override CETTE
# dépendance (et elle seule) sur chaque app créée par les tests. Les tests de
# rejet d'authentification passent par `authenticate` (non touché ici) et les
# gardes RBAC (`require_admin`/`require_curator`) restent effectives.
_TEST_PRINCIPAL = _auth.Principal(
    user_id=uuid.UUID(int=1),
    email="test@zolaos.test",
    tenant_id="local",
    country="cg",
    auth_method="jwt",
    scopes=(),
    role="admin",
)

_orig_create_app = _main.create_app


def _create_app_test_authed(*args, **kwargs):  # type: ignore[no-untyped-def]
    app = _orig_create_app(*args, **kwargs)
    # setdefault : un test qui veut le vrai comportement (401/403) peut poser son
    # propre override AVANT, ou retirer celui-ci (cf. `tests/test_box_auth.py`).
    app.dependency_overrides.setdefault(_auth.require_box_auth, lambda: _TEST_PRINCIPAL)
    app.dependency_overrides.setdefault(_auth.require_box_csrf, lambda: None)
    # Édition de la personnalisation (PUT /v1/config) : réservée à un rôle privilégié.
    # _TEST_PRINCIPAL est admin → autorisé ; un test dédié vérifie le rejet client.
    from zolaos.api.v1.config import require_config_editor as _require_config_editor

    app.dependency_overrides.setdefault(_require_config_editor, lambda: _TEST_PRINCIPAL)
    return app


# Patch au niveau module : conftest est importé AVANT les modules de test, donc
# leur `from zolaos.api.main import create_app` récupère cette version.
_main.create_app = _create_app_test_authed
create_app = _create_app_test_authed
# Version SANS bypass d'auth, pour les tests qui vérifient le rejet 401.
create_app_no_auth = _orig_create_app


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
