"""Tests d'application RÉELLE de l'entitlement au montage (`create_app`).

`resolve_box_modules` ne sert à rien si `api/main.py` ne l'applique pas : ces
tests émettent une vraie licence signée (tier `starter` → module `erp` seul),
construisent l'app en profil `box` avec `ENTITLEMENT_ENFORCED=True`, et
inspectent `app.openapi()["paths"]` pour prouver qu'un module non couvert est
absent de l'API (404, pas juste masqué) — même méthode que
`tests/test_engine_profile.py` (aucun réseau/DB/Redis nécessaire).

Note de mapping : le router `hr.py` (module vendable `sirh`) est monté sous le
préfixe `/v1/erp/...` (partagé avec le router `erp` proprement dit, module
`erp`). On distingue donc les deux par des chemins précis plutôt que par un
simple `startswith("/v1/erp")` : `/v1/erp/payroll/compute` (module `erp`) doit
rester présent en tier `starter`, alors que `/v1/erp/employees` (module
`sirh`, router `hr.py`) doit disparaître.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from zolaos.api.main import create_app
from zolaos.core.settings import Settings
from zolaos.licensing.entitlement import Entitlement, sign_entitlement


def _make_rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pem_public = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return pem_private, pem_public


@pytest.fixture()
def keypair() -> tuple[str, str]:
    return _make_rsa_keypair()


def _base_settings_kwargs() -> dict:
    return {
        "ZOLAOS_PROFILE": "box",
        "POSTGRES_PASSWORD_APP": "x",
        "POSTGRES_PASSWORD_MIGRATIONS": "x",
        "JWT_SECRET": "x" * 32,
    }


def _issue_starter_license(*, private_key_pem: str) -> str:
    now = datetime.now(UTC)
    ent = Entitlement(
        tenant_id="acme-sarl",
        tier="starter",  # {"erp"} seul, cf. TIERS
        modules=[],
        license_id="lic-starter-test",
        issued_at=now,
        expires_at=now + timedelta(days=365),
    )
    return sign_entitlement(ent, private_key_pem=private_key_pem)


def test_starter_tier_enforced_mounts_only_erp_module(keypair: tuple[str, str]) -> None:
    priv, pub = keypair
    token = _issue_starter_license(private_key_pem=priv)

    settings = Settings(
        ENTITLEMENT_ENFORCED=True,
        ENTITLEMENT_PUBLIC_KEY=pub,
        ENTITLEMENT_LICENSE_JWT=token,
        **_base_settings_kwargs(),
    )
    app = create_app(settings=settings)
    paths = set(app.openapi()["paths"].keys())

    # Présent : module `erp` (couvert par le tier starter).
    assert "/v1/erp/payroll/compute" in paths
    # Le plan de mission n'est pas un module vendable — toujours monté.
    assert any(p.startswith("/v1/box") for p in paths)

    # Absents : modules non couverts par starter.
    assert "/v1/erp/employees" not in paths  # module `sirh` (router hr.py)
    assert not any(p.startswith("/v1/cyber") for p in paths)
    assert not any(p.startswith("/v1/fintech") for p in paths)
    assert not any(p.startswith("/v1/code") for p in paths)
    assert not any(p.startswith("/v1/crm") for p in paths)
    assert not any(p.startswith("/v1/bi") for p in paths)
    assert not any(p.startswith("/v1/mkt") for p in paths)  # marketing
    assert not any(p.startswith("/v1/grc") for p in paths)


def test_enforcement_disabled_mounts_every_module() -> None:
    """`ENTITLEMENT_ENFORCED=False` (défaut) : comportement dev/actuel inchangé
    — tous les modules montés, quelle que soit l'absence de licence."""
    settings = Settings(ENTITLEMENT_ENFORCED=False, **_base_settings_kwargs())
    app = create_app(settings=settings)
    paths = set(app.openapi()["paths"].keys())

    assert "/v1/erp/payroll/compute" in paths
    assert "/v1/erp/employees" in paths
    assert any(p.startswith("/v1/cyber") for p in paths)
    assert any(p.startswith("/v1/fintech") for p in paths)
    assert any(p.startswith("/v1/code") for p in paths)
    assert any(p.startswith("/v1/crm") for p in paths)
    assert any(p.startswith("/v1/bi") for p in paths)
    assert any(p.startswith("/v1/mkt") for p in paths)
    assert any(p.startswith("/v1/grc") for p in paths)


def test_enforced_without_license_mounts_nothing_fail_closed(keypair: tuple[str, str]) -> None:
    """Enforcement actif mais aucune licence déposée → fail-closed : aucun
    module vertical monté (mais le plan de mission `box` reste, il n'est pas
    un module vendable)."""
    _priv, pub = keypair
    settings = Settings(
        ENTITLEMENT_ENFORCED=True,
        ENTITLEMENT_PUBLIC_KEY=pub,
        ENTITLEMENT_LICENSE_JWT="",
        **_base_settings_kwargs(),
    )
    app = create_app(settings=settings)
    paths = set(app.openapi()["paths"].keys())

    assert any(p.startswith("/v1/box") for p in paths)
    assert "/v1/erp/payroll/compute" not in paths
    assert not any(p.startswith("/v1/cyber") for p in paths)
    assert not any(p.startswith("/v1/crm") for p in paths)
