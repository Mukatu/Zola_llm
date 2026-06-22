"""Personnalisation par tenant (addendum UX/Personnalisation).

Configuration **déterministe** par client (`box`) que le frontend consomme pour
s'afficher : modules activés, branding, langue, champs, connecteurs. Le profil
`cortex` (consultant Polaris) a une **config uniforme imposée** — pas de
personnalisation client.

Stockage abstrait (`ConfigStore`) : en mémoire ici, DB (`core.tenant_config`)
plus tard, sans changer le service.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Catalogue des modules (référentiel — valide la personnalisation)
# ---------------------------------------------------------------------------

MODULE_CATALOGUE: dict[str, tuple[str, ...]] = {
    "sante": ("pharmacology", "diagnosis", "case"),
    "droit": ("ohada", "travail_cg", "fiscal_cg", "admin_cg", "social_cg",
              "civil_cg", "penal_cg", "ip_oapi", "data_protection_cg"),
    "erp": ("rh", "paie", "finance", "compta", "projets_ong",
            "supply_chain", "achats", "moyens_generaux", "secretariat_societaire", "hse"),
    "bi": ("pilotage",),
    "commercial": ("crm",),
    "marketing": ("campagnes",),
    "grc": ("conformite", "audit_institutionnel", "reporting_bailleurs"),
    "fintech": ("scoring", "kyc"),
    "cyber": ("defense",),
    "engineering": ("code",),
}


def all_module_codes() -> frozenset[str]:
    """Ensemble des codes `pole.module` valides."""
    return frozenset(f"{pole}.{m}" for pole, mods in MODULE_CATALOGUE.items() for m in mods)


# Config uniforme du consultant Polaris (cortex) — outils de mission.
CORTEX_MODULES: tuple[str, ...] = (
    "polaris.missions", "polaris.audit", "polaris.reports",
)

# Modules activés par défaut pour un nouveau client (box).
DEFAULT_BOX_MODULES: tuple[str, ...] = (
    "droit.ohada", "droit.travail_cg", "droit.fiscal_cg",
    "erp.rh", "erp.finance", "bi.pilotage",
)


class PersonalizationError(ValueError):
    """Configuration de personnalisation invalide."""


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------

class Branding(BaseModel):
    model_config = {"extra": "forbid"}

    nom_affichage: str = "ZolaOS"
    couleur_primaire: str = Field(default="#0B5FFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_uri: str | None = None


class TenantConfig(BaseModel):
    model_config = {"extra": "forbid"}

    tenant_id: str | None = None
    profil: Literal["box", "cortex"] = "box"
    personnalisable: bool = True
    modules_actifs: list[str] = Field(default_factory=list)
    branding: Branding = Field(default_factory=Branding)
    locale: Literal["fr", "ln", "kg"] = "fr"
    champs_personnalises: dict[str, str] = Field(default_factory=dict)
    connecteurs_actifs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stockage des overrides (pluggable)
# ---------------------------------------------------------------------------

class ConfigStore(Protocol):
    def get(self, tenant_id: str) -> dict[str, Any] | None: ...
    def set(self, tenant_id: str, overrides: dict[str, Any]) -> None: ...


class InMemoryConfigStore:
    """Store par défaut (tests / dev). DB plus tard."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def get(self, tenant_id: str) -> dict[str, Any] | None:
        return self._data.get(tenant_id)

    def set(self, tenant_id: str, overrides: dict[str, Any]) -> None:
        self._data[tenant_id] = overrides


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class TenantConfigService:
    """Résout la configuration effective d'un tenant selon le profil."""

    def __init__(self, store: ConfigStore | None = None) -> None:
        self._store: ConfigStore = store or InMemoryConfigStore()

    def catalogue(self) -> frozenset[str]:
        return all_module_codes()

    def validate_modules(self, modules: list[str]) -> None:
        inconnus = sorted(set(modules) - all_module_codes())
        if inconnus:
            raise PersonalizationError(f"Modules inconnus au catalogue : {inconnus}")

    def cortex_config(self) -> TenantConfig:
        """Config consultant **uniforme** (identique pour tous)."""
        return TenantConfig(
            profil="cortex",
            personnalisable=False,
            modules_actifs=list(CORTEX_MODULES),
            branding=Branding(nom_affichage="ZolaCortex — Polaris"),
            locale="fr",
        )

    def default_box_config(self, tenant_id: str | None = None) -> TenantConfig:
        return TenantConfig(
            tenant_id=tenant_id,
            profil="box",
            personnalisable=True,
            modules_actifs=list(DEFAULT_BOX_MODULES),
        )

    def set_overrides(self, tenant_id: str, overrides: dict[str, Any]) -> None:
        """Enregistre la personnalisation d'un client (box). Valide les modules."""
        if "modules_actifs" in overrides:
            self.validate_modules(overrides["modules_actifs"])
        self._store.set(tenant_id, overrides)

    def resolve(self, profil: str, *, tenant_id: str | None = None) -> TenantConfig:
        """Config effective. `cortex` = uniforme ; `box` = défauts + overrides du tenant."""
        if profil == "cortex":
            return self.cortex_config()
        config = self.default_box_config(tenant_id)
        if tenant_id is not None:
            overrides = self._store.get(tenant_id)
            if overrides:
                merged = config.model_dump()
                merged.update(overrides)
                config = TenantConfig.model_validate(merged)
        self.validate_modules(config.modules_actifs)
        return config
