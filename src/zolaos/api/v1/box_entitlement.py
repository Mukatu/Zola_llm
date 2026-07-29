"""Statut & refresh de l'entitlement — côté BOX.

Expose l'état d'entitlement **courant** (jeu de modules autorisés, application à
chaud) et un déclencheur de rafraîchissement manuel. Le refresh automatique passe
par le tunnel (`tunnel.agent`) ; cet endpoint sert l'observabilité et un forçage
ops (ex. licence remplacée sur disque hors tunnel).

Monté uniquement en profil `box`, sous les gardes du plan de données (`_box_auth`).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from zolaos.api.entitlement_gate import get_entitlement_state
from zolaos.core.logging import get_logger

_log = get_logger("zolaos.api.v1.box_entitlement")

router = APIRouter(prefix="/v1/box/entitlement", tags=["box", "entitlement"])


class EntitlementStatus(BaseModel):
    # None = enforcement désactivé (tous les modules montés). Sinon, jeu autorisé courant.
    enforced: bool
    allowed_modules: list[str] | None


def _status(request: Request) -> EntitlementStatus:
    state = get_entitlement_state(request)
    allowed = state.allowed if state is not None else None
    return EntitlementStatus(
        enforced=allowed is not None,
        allowed_modules=None if allowed is None else sorted(allowed),
    )


@router.get("", response_model=EntitlementStatus, summary="Modules autorisés courants (box)")
async def get_entitlement(request: Request) -> EntitlementStatus:
    return _status(request)


class RefreshResult(EntitlementStatus):
    changed: bool


@router.post("/refresh", response_model=RefreshResult, summary="Recharger la licence (à chaud)")
async def refresh_entitlement(request: Request) -> RefreshResult:
    """Relit la licence et recalcule le jeu autorisé (application à chaud). Une
    révocation prend effet immédiatement (les modules retirés passent en 404).

    Réutilise les settings avec lesquels l'app a été construite (portés par l'état)."""
    state = get_entitlement_state(request)
    changed = state.refresh() if state is not None else False
    if changed:
        _log.info("entitlement.manual_refresh.changed")
    st = _status(request)
    return RefreshResult(enforced=st.enforced, allowed_modules=st.allowed_modules, changed=changed)
