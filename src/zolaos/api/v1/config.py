"""Endpoint de configuration / personnalisation (addendum UX/Personnalisation).

`GET /v1/config` : le frontend lit la **config effective** au démarrage pour
s'afficher. Profil `cortex` → config consultant **uniforme** ; profil `box` →
config personnalisée du client (défauts + overrides). Monté dans les deux profils.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from zolaos.core.personalization import TenantConfig, TenantConfigService
from zolaos.core.settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["config"])

_service = TenantConfigService()


def get_config_service() -> TenantConfigService:
    return _service


@router.get("/config", response_model=TenantConfig, summary="Configuration effective (personnalisation)")
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
