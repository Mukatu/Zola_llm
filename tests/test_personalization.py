"""Tests personnalisation par tenant (addendum UX) + endpoint /v1/config."""

from __future__ import annotations

import pytest

from zolaos.core.personalization import (
    DEFAULT_BOX_MODULES,
    PersonalizationError,
    TenantConfigService,
)


@pytest.fixture
def service() -> TenantConfigService:
    return TenantConfigService()


def test_cortex_config_is_uniform(service: TenantConfigService) -> None:
    cfg = service.resolve("cortex", tenant_id="ignored")
    assert cfg.profil == "cortex"
    assert cfg.personnalisable is False
    assert "polaris.missions" in cfg.modules_actifs
    # tenant_id ignoré : pas de personnalisation côté consultant
    assert cfg.tenant_id is None


def test_box_default_config(service: TenantConfigService) -> None:
    cfg = service.resolve("box", tenant_id="client-1")
    assert cfg.profil == "box"
    assert cfg.personnalisable is True
    assert set(cfg.modules_actifs) == set(DEFAULT_BOX_MODULES)


def test_box_overrides_applied(service: TenantConfigService) -> None:
    service.set_overrides("client-1", {
        "modules_actifs": ["sante.pharmacology", "erp.compta"],
        "branding": {"nom_affichage": "Polyclinique X", "couleur_primaire": "#00AA55"},
        "locale": "fr",
    })
    cfg = service.resolve("box", tenant_id="client-1")
    assert cfg.modules_actifs == ["sante.pharmacology", "erp.compta"]
    assert cfg.branding.nom_affichage == "Polyclinique X"
    assert cfg.branding.couleur_primaire == "#00AA55"


def test_unknown_module_rejected(service: TenantConfigService) -> None:
    with pytest.raises(PersonalizationError):
        service.set_overrides("client-2", {"modules_actifs": ["pole.inexistant"]})


def test_catalogue_contains_new_poles(service: TenantConfigService) -> None:
    cat = service.catalogue()
    for code in ("bi.pilotage", "commercial.crm", "marketing.campagnes"):
        assert code in cat


def test_config_endpoint_returns_box_config(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/v1/config")
    assert r.status_code == 200
    body = r.json()
    assert body["profil"] == "box"
    assert "droit.ohada" in body["modules_actifs"]
    assert body["personnalisable"] is True
