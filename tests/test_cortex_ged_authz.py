"""Régression sécurité — les lectures GED du cortex exigent une authentification.

Un défaut avait laissé `GET /v1/cortex/ged/templates` et `.../deliverables` (ainsi
que leurs variantes `/{id}`) accessibles SANS jeton : seul le profil `cortex` était
vérifié (dépendance de router), pas l'authentification de l'appelant. On verrouille :
sans jeton ni cookie, ces lectures doivent renvoyer 401 (la dépendance `authenticate`
tombe avant le handler, donc avant toute lecture en base).
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from zolaos.core.settings import get_settings
from zolaos.db.session import reset_engine_cache


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


@pytest.mark.parametrize(
    "path",
    [
        "/v1/cortex/ged/deliverables",
        "/v1/cortex/ged/templates",
        f"/v1/cortex/ged/deliverables/{uuid.uuid4()}",
        f"/v1/cortex/ged/templates/{uuid.uuid4()}",
    ],
)
@pytest.mark.asyncio
async def test_ged_read_requires_auth(path: str) -> None:
    from zolaos.api.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(path)
    assert r.status_code == 401, f"{path} doit exiger une authentification (reçu {r.status_code})"
