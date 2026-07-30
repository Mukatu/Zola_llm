"""Tests de l'endpoint /v1/config (GET/PUT personnalisation) via TestClient."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from zolaos.api.auth import Principal, authenticate
from zolaos.api.v1.config import require_config_editor
from zolaos.core.personalization import filter_codes_by_entitlement
from zolaos.core.settings import get_settings
from zolaos.licensing.entitlement import Entitlement, sign_entitlement


def _keypair() -> tuple[str, str]:
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        k.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return priv, pub


def _principal(role: str) -> Principal:
    return Principal(
        user_id=__import__("uuid").UUID(int=7),
        email="x@zolaos.test",
        tenant_id="local",
        country="cg",
        auth_method="jwt",
        role=role,
    )


def test_get_default_config(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["profil"] == "box"


def test_put_persists_personalization_not_modules(client) -> None:  # type: ignore[no-untyped-def]
    # Le client personnalise branding/langue…
    upd = {
        "tenant_id": "t-test",
        "modules_actifs": ["sante.pharmacology", "erp.compta"],  # tentative d'auto-octroi
        "branding": {"nom_affichage": "Clinique X", "couleur_primaire": "#00AA55"},
        "locale": "fr",
    }
    r = client.put("/v1/config", json=upd)
    assert r.status_code == 200
    body = r.json()
    assert body["branding"]["nom_affichage"] == "Clinique X"
    # …mais NE PEUT PAS s'octroyer de modules : `modules_actifs` envoyé est IGNORÉ
    # (champ retiré de ConfigUpdate — la distribution est un entitlement Polaris).
    assert set(body["modules_actifs"]) != {"sante.pharmacology", "erp.compta"}
    # Persisté : un GET avec le même tenant retourne les overrides de personnalisation.
    r2 = client.get("/v1/config", params={"tenant_id": "t-test"})
    assert r2.json()["branding"]["couleur_primaire"] == "#00AA55"


def test_client_cannot_grant_modules_via_config(client) -> None:  # type: ignore[no-untyped-def]
    # L'ancien trou (« lamentable ») : le client réglait ses propres modules.
    # Désormais impossible — le champ n'existe plus, la valeur est sans effet.
    before = set(client.get("/v1/config", params={"tenant_id": "t3"}).json()["modules_actifs"])
    r = client.put("/v1/config", json={"tenant_id": "t3", "modules_actifs": ["cyber.defense"]})
    assert r.status_code == 200
    after = set(r.json()["modules_actifs"])
    assert "cyber.defense" not in after  # le client ne s'est rien octroyé
    assert after == before  # inchangé


# ---------------------------------------------------------------------------
# Filtrage de modules_actifs par l'entitlement (synchro affichage)
# ---------------------------------------------------------------------------
def test_filter_codes_by_entitlement_unit() -> None:
    codes = ["droit.ohada", "erp.finance", "erp.rh", "bi.pilotage", "cyber.defense"]
    # Enforcement off (None) → rien filtré.
    assert filter_codes_by_entitlement(codes, None) == codes
    # Tier starter (erp seul) : garde droit.* (non gardé) + erp.finance (erp) ; retire
    # erp.rh (sirh), bi.pilotage (bi), cyber.defense (cyber).
    kept = filter_codes_by_entitlement(codes, frozenset({"erp"}))
    assert "droit.ohada" in kept
    assert "erp.finance" in kept
    assert "erp.rh" not in kept
    assert "bi.pilotage" not in kept
    assert "cyber.defense" not in kept


def test_get_config_filters_modules_by_entitlement() -> None:
    """En profil box avec enforcement + licence starter, GET /v1/config ne montre
    que les modules réellement couverts (l'endpoint lit get_settings global → on
    passe par l'environnement, comme les autres tests de profil)."""
    from tests.conftest import create_app

    priv, pub = _keypair()
    now = datetime.now(UTC)
    token = sign_entitlement(
        Entitlement(
            tenant_id="acme",
            tier="starter",
            modules=[],
            license_id="lic-cfg",
            issued_at=now,
            expires_at=now + timedelta(days=30),
        ),
        private_key_pem=priv,
    )
    prev = {k: os.environ.get(k) for k in ("ZOLAOS_PROFILE", "ENTITLEMENT_ENFORCED")}
    os.environ["ZOLAOS_PROFILE"] = "box"
    os.environ["ENTITLEMENT_ENFORCED"] = "true"
    os.environ["ENTITLEMENT_PUBLIC_KEY"] = pub
    os.environ["ENTITLEMENT_LICENSE_JWT"] = token
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as c:
            mods = set(c.get("/v1/config").json()["modules_actifs"])
        assert "erp.finance" in mods  # module erp couvert par starter
        assert "droit.ohada" in mods  # corpus de référence, non soumis à entitlement
        assert "erp.rh" not in mods  # sirh, non couvert
        assert "bi.pilotage" not in mods  # bi, non couvert
    finally:
        for k in ("ENTITLEMENT_PUBLIC_KEY", "ENTITLEMENT_LICENSE_JWT"):
            os.environ.pop(k, None)
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# RBAC sur PUT /v1/config
# ---------------------------------------------------------------------------
def test_put_config_forbidden_for_client_role() -> None:
    from tests.conftest import create_app

    app = create_app()
    # On teste la vraie garde : retirer l'override par défaut, forcer un rôle client.
    app.dependency_overrides.pop(require_config_editor, None)
    app.dependency_overrides[authenticate] = lambda: _principal("client")
    with TestClient(app) as c:
        r = c.put("/v1/config", json={"tenant_id": "t", "locale": "fr"})
    assert r.status_code == 403
    assert r.json()["detail"] == "config_editor_role_required"


def test_put_config_requires_authentication() -> None:
    from tests.conftest import create_app

    app = create_app()
    app.dependency_overrides.pop(require_config_editor, None)  # vraie garde → authenticate
    with TestClient(app) as c:
        r = c.put("/v1/config", json={"tenant_id": "t", "locale": "fr"})
    assert r.status_code == 401
