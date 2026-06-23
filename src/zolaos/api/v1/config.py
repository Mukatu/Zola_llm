"""Endpoint de configuration / personnalisation (addendum UX/Personnalisation).

`GET /v1/config` : le frontend lit la **config effective** au démarrage pour
s'afficher. Profil `cortex` → config consultant **uniforme** ; profil `box` →
config personnalisée du client (défauts + overrides). Monté dans les deux profils.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from zolaos.core.personalization import PersonalizationError, TenantConfig, TenantConfigService
from zolaos.core.settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["config"])

_service = TenantConfigService()


def get_config_service() -> TenantConfigService:
    return _service


class ConfigUpdate(BaseModel):
    """Personnalisation partielle d'un tenant (box uniquement)."""

    tenant_id: str = Field(default="local")
    modules_actifs: list[str] | None = None
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
    """
    return service.resolve(settings.ZOLAOS_PROFILE, tenant_id=tenant_id)


@router.put("/config", response_model=TenantConfig, summary="Enregistrer la personnalisation (box)")
async def put_config(
    update: ConfigUpdate,
    settings: Settings = Depends(get_settings),
    service: TenantConfigService = Depends(get_config_service),
) -> TenantConfig:
    """Met à jour la personnalisation d'un client (profil box uniquement).

    Le profil `cortex` est uniforme (non personnalisable) → 403.
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
