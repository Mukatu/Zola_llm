"""Garde runtime d'entitlement (côté BOX) — application À CHAUD.

Le montage conditionnel (`api/main.py`) décide au démarrage quels modules exister ;
cette garde, ajoutée en dépendance sur chaque module monté, vérifie à CHAQUE requête
le jeu de modules **courant** (`EntitlementState`, cf. `licensing/state.py`). Elle
permet de **révoquer un module à chaud** : après un refresh de licence (tunnel), un
module retiré passe en 404 sans redémarrer.

Au démarrage, `allowed` == le jeu monté → la garde est un no-op ; elle ne mord que
si l'état est réduit ensuite. `allowed is None` (enforcement off) → passe toujours.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, status

from zolaos.licensing.state import EntitlementState


def get_entitlement_state(request: Request) -> EntitlementState | None:
    """État d'entitlement porté par l'app (posé dans `create_app`). None si absent."""
    return getattr(request.app.state, "entitlement_state", None)


def require_module(module: str) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """Fabrique une dépendance qui 404 si `module` n'est pas couvert par l'état courant."""

    async def _guard(request: Request) -> None:
        state = get_entitlement_state(request)
        # Pas d'état (profil non-box / non initialisé) → ne bloque pas.
        if state is not None and not state.is_allowed(module):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="module_not_licensed")

    return _guard
