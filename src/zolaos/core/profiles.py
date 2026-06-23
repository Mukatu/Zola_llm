"""Profils de déploiement ZolaOS — Polaris addendum V3 (#56).

Deux profils, même codebase :
  - `box`    : déploiement chez l'entreprise cliente (Zolabox). Routes restreintes,
               agents génératifs V2.2 actifs, pas d'overlay Polaris, pas de
               génération de rapport cabinet, pas d'accès cross-tenants.
  - `cortex` : déploiement chez le cabinet conseil Polaris (Zolacortex). Tout
               ce que `box` fait, plus : overlays Polaris (OUTPUT_FORMAT strict),
               génération de rapports `.docx`, gestion missions, accès éphémère
               aux Zolabox clientes via token mission.

Le profil est défini par `Settings.ZOLAOS_PROFILE` (env var `ZOLAOS_PROFILE`).
Défaut : `box` (moindre privilège).

Usage :
    from zolaos.core.profiles import Profile, require_profile, current_profile

    # Vérification ponctuelle dans du code applicatif :
    require_profile(Profile.CORTEX)

    # Décorateur sur fonction (sync ou async) :
    @cortex_only
    async def generate_audit_report(...): ...

    # Endpoint FastAPI :
    @router.get("/missions", dependencies=[Depends(require_cortex)])
    async def list_missions(...): ...
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from zolaos.core.settings import get_settings

F = TypeVar("F", bound=Callable[..., Any])


class Profile(str, Enum):
    BOX = "box"
    CORTEX = "cortex"


class ProfileError(RuntimeError):
    """Tentative d'exécuter une opération dans le mauvais profil."""


def current_profile() -> Profile:
    """Lit le profil actif depuis les Settings (mise en cache via lru_cache de Settings)."""
    return Profile(get_settings().ZOLAOS_PROFILE)


def require_profile(*allowed: Profile) -> Profile:
    """Lève ProfileError si le profil courant n'est pas dans `allowed`. Retourne le profil sinon."""
    cur = current_profile()
    if cur not in allowed:
        allowed_str = ", ".join(p.value for p in allowed)
        raise ProfileError(
            f"Opération réservée au(x) profil(s) [{allowed_str}], "
            f"profil courant : '{cur.value}'."
        )
    return cur


def _profile_decorator(*allowed: Profile) -> Callable[[F], F]:
    """Décorateur qui force le profil — gère sync ET async transparemment."""

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                require_profile(*allowed)
                return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            require_profile(*allowed)
            return fn(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def cortex_only(fn: F) -> F:
    """Raccourci : `@cortex_only` ≡ `@_profile_decorator(Profile.CORTEX)`."""
    return _profile_decorator(Profile.CORTEX)(fn)


def box_only(fn: F) -> F:
    """Raccourci : `@box_only` ≡ `@_profile_decorator(Profile.BOX)`."""
    return _profile_decorator(Profile.BOX)(fn)


# ---------------------------------------------------------------------------
# Dépendances FastAPI (à importer depuis les routers Cortex/Box)
# ---------------------------------------------------------------------------


def require_cortex() -> Profile:
    """Dépendance FastAPI : autorise uniquement le profil cortex."""
    return require_profile(Profile.CORTEX)


def require_box() -> Profile:
    """Dépendance FastAPI : autorise uniquement le profil box."""
    return require_profile(Profile.BOX)
