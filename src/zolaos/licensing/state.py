"""État d'entitlement vivant (en mémoire) — côté BOX, pour l'application À CHAUD.

`resolve_box_modules(settings)` calcule le jeu de modules au démarrage ; il sert au
**montage** (un module non couvert n'est pas monté → absent de l'OpenAPI). Mais le
montage est figé pour la vie du process. Pour qu'une **révocation** (ou une réduction
de licence) prenne effet **sans redémarrer**, on tient en plus cet état mutable,
consulté par une garde runtime sur chaque module monté (`api.entitlement_gate`).

Le refresh du tunnel (`tunnel.agent._apply_license`, MÊME process que l'app) appelle
`refresh()` après avoir réécrit le fichier de licence → la garde reflète aussitôt le
nouveau jeu. Sens de l'application à chaud :

- **Réduction / révocation** : un module monté au boot mais retiré de la licence est
  aussitôt **404** (fail-closed immédiat). C'est le cas critique.
- **Extension** : un module *neuf* (jamais monté au boot) n'est pas exposable à chaud
  (sa route n'existe pas) → nécessite un redémarrage. Sens sûr (fail-open = restart).

`allowed is None` = enforcement désactivé (`ENTITLEMENT_ENFORCED=False`) : la garde
laisse tout passer (comportement dev/actuel inchangé).
"""

from __future__ import annotations

from zolaos.core.logging import get_logger
from zolaos.licensing.entitlement import resolve_box_modules

_log = get_logger("zolaos.licensing.state")


class EntitlementState:
    """Jeu de modules autorisés courant. `allowed=None` → enforcement off (tout permis)."""

    def __init__(self, allowed: frozenset[str] | None, settings=None) -> None:  # type: ignore[no-untyped-def]
        self.allowed = allowed
        # Settings d'origine : `refresh()` les réutilise (source unique de vérité).
        # Indispensable pour ne pas retomber sur les settings globaux (env) qui
        # peuvent différer de ceux avec lesquels l'app a été construite.
        self._settings = settings

    @classmethod
    def from_settings(cls, settings) -> EntitlementState:  # type: ignore[no-untyped-def]
        return cls(resolve_box_modules(settings), settings)

    def is_allowed(self, module: str) -> bool:
        """Vrai si le module est couvert (ou si l'enforcement est désactivé)."""
        return self.allowed is None or module in self.allowed

    def refresh(self) -> bool:
        """Recharge la licence et recalcule le jeu autorisé. Retourne True si changé.

        Réutilise les settings d'origine. Assignation atomique (mono-thread asyncio) :
        les gardes lisent `allowed` sans verrou. `resolve_box_modules` relit le
        fichier/JWT à chaque appel, donc un fichier réécrit par le refresh tunnel est
        bien pris en compte. No-op (False) si aucun settings n'a été mémorisé."""
        if self._settings is None:
            return False
        old = self.allowed
        new = resolve_box_modules(self._settings)
        self.allowed = new
        changed = old != new
        if changed:
            _log.info(
                "entitlement.hot_refresh",
                before=None if old is None else sorted(old),
                after=None if new is None else sorted(new),
            )
        return changed
