"""Endpoint de configuration / personnalisation (addendum UX/Personnalisation).

`GET /v1/config` : le frontend lit la **config effective** au démarrage pour
s'afficher. Profil `cortex` → config consultant **uniforme** ; profil `box` →
config personnalisée du client (défauts + overrides). Monté dans les deux profils.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from zolaos.api.auth import Principal, authenticate
from zolaos.core.personalization import (
    PersonalizationError,
    TenantConfig,
    TenantConfigService,
    filter_codes_by_entitlement,
)
from zolaos.core.settings import Settings, get_settings
from zolaos.licensing import resolve_box_modules

router = APIRouter(prefix="/v1", tags=["config"])

_service = TenantConfigService()

# Rôles autorisés à éditer la personnalisation d'un tenant. Un simple `client`
# (ou un anonyme) ne peut pas modifier la config — seul un rôle privilégié le peut.
_CONFIG_EDITOR_ROLES = ("admin", "consultant")


def get_config_service() -> TenantConfigService:
    return _service


async def require_config_editor(principal: Principal = Depends(authenticate)) -> Principal:
    """Réserve l'édition de la personnalisation (PUT) à un rôle privilégié.

    401 si non authentifié (via `authenticate`), 403 si le rôle n'est pas
    admin/consultant. Découplée pour permettre un override de test dédié."""
    if principal.role not in _CONFIG_EDITOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="config_editor_role_required"
        )
    return principal


class ConfigUpdate(BaseModel):
    """Personnalisation partielle d'un tenant (box uniquement).

    NB : `modules_actifs` a été RETIRÉ délibérément — la distribution des modules
    est un ENTITLEMENT signé par Polaris (cf. `zolaos.licensing`), appliqué au
    montage des routers, JAMAIS réglable par le client. Ce endpoint ne gère plus
    que la vraie personnalisation (branding, langue, champs, connecteurs) ; il ne
    peut plus octroyer de modules. Un `modules_actifs` envoyé par un client est
    ignoré (hors du modèle)."""

    tenant_id: str = Field(default="local")
    branding: dict[str, Any] | None = None
    locale: str | None = None
    champs_personnalises: dict[str, str] | None = None
    connecteurs_actifs: list[str] | None = None


@router.get(
    "/config", response_model=TenantConfig, summary="Configuration effective (personnalisation)"
)
async def get_config(
    tenant_id: str | None = None,
    settings: Settings = Depends(get_settings),
    service: TenantConfigService = Depends(get_config_service),
) -> TenantConfig:
    """Retourne la config effective selon le profil de déploiement.

    - `box` : modules/branding/langue du client (`?tenant_id=` pour ses overrides).
    - `cortex` : config consultant uniforme (non personnalisable).

    En profil `box`, `modules_actifs` est **filtré par l'entitlement réel**
    (`resolve_box_modules`) : l'UI n'affiche jamais un module que le serveur
    n'expose pas (enforcement désactivé → aucun filtrage)."""
    config = service.resolve(settings.ZOLAOS_PROFILE, tenant_id=tenant_id)
    if settings.ZOLAOS_PROFILE == "box":
        config.modules_actifs = filter_codes_by_entitlement(
            config.modules_actifs, resolve_box_modules(settings)
        )
    return config


@router.put("/config", response_model=TenantConfig, summary="Enregistrer la personnalisation (box)")
async def put_config(
    update: ConfigUpdate,
    settings: Settings = Depends(get_settings),
    service: TenantConfigService = Depends(get_config_service),
    _editor: Principal = Depends(require_config_editor),
) -> TenantConfig:
    """Met à jour la personnalisation d'un client (profil box uniquement).

    Réservé à un rôle privilégié (`require_config_editor`) : un simple client ne
    peut pas modifier la config. Le profil `cortex` est uniforme → 403.
    """
    if settings.ZOLAOS_PROFILE == "cortex":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="config_cortex_non_personnalisable",
        )
    overrides = update.model_dump(exclude_none=True, exclude={"tenant_id"})
    try:
        service.set_overrides(update.tenant_id, overrides)
    except PersonalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return service.resolve("box", tenant_id=update.tenant_id)
