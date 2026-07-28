"""Tests du profil de déploiement `engine` (moteur souverain headless).

Le profil `engine` expose UNIQUEMENT la surface générique du moteur :
`/v1/query`, `/v1/query/stream`, `/v1/agents` + l'authentification
(`/v1/auth/*`, dont le auto-login de dev qui partage le même préfixe) +
`/health` + `/metrics`. Ni les blocs verticaux `box` (erp, code, cyber, ...)
ni le cockpit `cortex` ne doivent être montés.

Vérifie aussi la non-régression : les profils `box` et `cortex` conservent
exactement les routers qu'ils montaient avant ce refactor (inspection de
`app.openapi()["paths"]`, aucune requête réseau, pas besoin de Redis/DB).
"""

from __future__ import annotations

from zolaos.api.main import create_app
from zolaos.core.settings import Settings


def _settings(profile: str) -> Settings:
    return Settings(
        ZOLAOS_PROFILE=profile,
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )


def _paths(profile: str) -> set[str]:
    app = create_app(settings=_settings(profile))
    return set(app.openapi()["paths"].keys())


def test_engine_profile_exposes_only_generic_engine_surface() -> None:
    paths = _paths("engine")

    # Présents : le cœur moteur générique + l'authentification universelle.
    assert "/v1/query" in paths
    assert "/v1/query/stream" in paths
    assert "/v1/agents" in paths
    assert "/v1/auth/login" in paths

    # Absents : tout module vertical box/cortex, ainsi que les préoccupations
    # applicatives box/cortex (config/feedback/kb/legal/commons) — pas du
    # moteur générique.
    assert not any(p.startswith("/v1/erp") for p in paths)
    assert not any(p.startswith("/v1/box") for p in paths)
    assert not any(p.startswith("/v1/kb") for p in paths)
    assert not any(p.startswith("/v1/code") for p in paths)
    assert not any(p.startswith("/v1/cyber") for p in paths)
    assert not any(p.startswith("/v1/cortex") for p in paths)
    assert not any(p.startswith("/v1/config") for p in paths)
    assert not any(p.startswith("/v1/feedback") for p in paths)
    assert not any(p.startswith("/v1/legal") for p in paths)
    assert not any(p.startswith("/v1/commons") for p in paths)


def test_box_profile_unchanged_still_exposes_verticals() -> None:
    paths = _paths("box")

    assert any(p.startswith("/v1/erp") for p in paths)
    assert any(p.startswith("/v1/code") for p in paths)
    assert any(p.startswith("/v1/cyber") for p in paths)
    # Toujours montés en box (non-régression du refactor).
    assert "/v1/query" in paths
    assert "/v1/agents" in paths
    assert "/v1/auth/login" in paths
    assert any(p.startswith("/v1/kb") for p in paths)
    assert any(p.startswith("/v1/config") for p in paths)

    # Toujours absent en box : le cockpit cortex.
    assert not any(p.startswith("/v1/cortex") for p in paths)


def test_cortex_profile_unchanged_box_still_absent() -> None:
    paths = _paths("cortex")

    # Comportement inchangé : cortex n'expose pas /v1/box.
    assert not any(p.startswith("/v1/box") for p in paths)
    assert not any(p.startswith("/v1/erp") for p in paths)
    # Toujours montés en cortex (transverse box+cortex, non-régression).
    assert "/v1/query" in paths
    assert "/v1/agents" in paths
    assert "/v1/auth/login" in paths
    assert any(p.startswith("/v1/kb") for p in paths)
    assert any(p.startswith("/v1/config") for p in paths)
