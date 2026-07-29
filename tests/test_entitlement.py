"""Tests unitaires de l'entitlement (licence commerciale signée Polaris).

Couvre les invariants de SÉCURITÉ du modèle : round-trip sign→verify,
infalsifiabilité (une clé publique — ou une autre paire — ne peut pas
signer/produire un jeton accepté), expiration, altération, le calcul
`effective_modules` (tier ∪ options, borné au catalogue) et le fail-closed de
`resolve_box_modules` (enforcement actif sans licence valide → aucun module).

Les paires RSA sont générées à la volée (aucune clé versionnée dans le dépôt).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from zolaos.core.settings import Settings
from zolaos.licensing.entitlement import (
    MODULES,
    Entitlement,
    EntitlementExpired,
    EntitlementInvalid,
    resolve_box_modules,
    sign_entitlement,
    verify_entitlement,
)


def _make_rsa_keypair() -> tuple[str, str]:
    """Génère une paire RSA de test et retourne (pem_private, pem_public)."""
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


def _entitlement(
    *,
    tenant_id: str = "acme-sarl",
    tier: str = "business",
    modules: list[str] | None = None,
    license_id: str = "lic-test-1",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Entitlement:
    now = datetime.now(UTC)
    return Entitlement(
        tenant_id=tenant_id,
        tier=tier,
        modules=modules or [],
        license_id=license_id,
        issued_at=issued_at or now,
        expires_at=expires_at or (now + timedelta(days=30)),
    )


# --------------------------------------------------------------------------
# Round-trip sign → verify
# --------------------------------------------------------------------------


def test_sign_then_verify_roundtrip_preserves_claims(keypair: tuple[str, str]) -> None:
    priv, pub = keypair
    ent = _entitlement(tenant_id="acme-sarl", tier="business", modules=["cyber"])

    token = sign_entitlement(ent, private_key_pem=priv)
    verified = verify_entitlement(token, public_key_pem=pub)

    assert verified.tenant_id == ent.tenant_id
    assert verified.tier == ent.tier
    assert verified.modules == ent.modules
    assert verified.license_id == ent.license_id
    # Les timestamps JWT sont en secondes : comparer à la seconde près.
    assert int(verified.issued_at.timestamp()) == int(ent.issued_at.timestamp())
    assert int(verified.expires_at.timestamp()) == int(ent.expires_at.timestamp())


# --------------------------------------------------------------------------
# Infalsifiabilité : forger sans la clé privée légitime est impossible
# --------------------------------------------------------------------------


def test_signing_with_the_public_key_is_rejected_by_jose(keypair: tuple[str, str]) -> None:
    """RS256 exige une clé PRIVÉE pour signer. Tenter de signer avec la clé
    publique (ce qu'une box malveillante tenterait si elle voulait forger un
    entitlement) échoue au niveau de la bibliothèque JWT elle-même."""
    _priv, pub = keypair
    ent = _entitlement()
    claims = {
        "iss": "polaris",
        "sub": ent.tenant_id,
        "tier": ent.tier,
        "modules": ent.modules,
        "jti": ent.license_id,
        "iat": int(ent.issued_at.timestamp()),
        "exp": int(ent.expires_at.timestamp()),
    }
    with pytest.raises(Exception):  # jose lève selon le backend crypto disponible
        jwt.encode(claims, pub, algorithm="RS256")


def test_token_signed_by_a_different_private_key_is_invalid(keypair: tuple[str, str]) -> None:
    """Une box ne possède que la clé PUBLIQUE légitime : un jeton signé par une
    AUTRE paire (ex. box malveillante forgeant sa propre licence) doit être
    rejeté à la vérification — c'est la preuve centrale d'infalsifiabilité."""
    _legit_priv, legit_pub = keypair
    rogue_priv, _rogue_pub = _make_rsa_keypair()

    ent = _entitlement(tier="full", modules=list(MODULES))
    forged_token = sign_entitlement(ent, private_key_pem=rogue_priv)

    with pytest.raises(EntitlementInvalid):
        verify_entitlement(forged_token, public_key_pem=legit_pub)


# --------------------------------------------------------------------------
# Expiration
# --------------------------------------------------------------------------


def test_expired_entitlement_raises_entitlement_expired(keypair: tuple[str, str]) -> None:
    priv, pub = keypair
    now = datetime.now(UTC)
    ent = _entitlement(
        issued_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),  # expiré depuis hier
    )
    token = sign_entitlement(ent, private_key_pem=priv)

    with pytest.raises(EntitlementExpired):
        verify_entitlement(token, public_key_pem=pub)


def test_is_expired_helper() -> None:
    now = datetime.now(UTC)
    past = _entitlement(expires_at=now - timedelta(seconds=1))
    future = _entitlement(expires_at=now + timedelta(days=1))
    assert past.is_expired(now=now) is True
    assert future.is_expired(now=now) is False


# --------------------------------------------------------------------------
# Altération du jeton
# --------------------------------------------------------------------------


def test_tampered_token_is_invalid(keypair: tuple[str, str]) -> None:
    priv, pub = keypair
    ent = _entitlement()
    token = sign_entitlement(ent, private_key_pem=priv)

    # Change un caractère au milieu du jeton (payload ou signature selon la
    # position) — dans tous les cas la signature ne doit plus correspondre.
    mid = len(token) // 2
    flipped_char = "a" if token[mid] != "a" else "b"
    tampered = token[:mid] + flipped_char + token[mid + 1 :]
    assert tampered != token

    with pytest.raises(EntitlementInvalid):
        verify_entitlement(tampered, public_key_pem=pub)


# --------------------------------------------------------------------------
# effective_modules()
# --------------------------------------------------------------------------


def test_effective_modules_tier_business_plus_cyber_option() -> None:
    ent = _entitlement(tier="business", modules=["cyber"])
    assert ent.effective_modules() == frozenset({"erp", "sirh", "bi", "crm", "marketing", "cyber"})


def test_effective_modules_ignores_unknown_option() -> None:
    ent = _entitlement(tier="business", modules=["cyber", "bidon"])
    expected = frozenset({"erp", "sirh", "bi", "crm", "marketing", "cyber"})
    assert ent.effective_modules() == expected
    assert "bidon" not in ent.effective_modules()


def test_effective_modules_unknown_tier_yields_only_options() -> None:
    ent = _entitlement(tier="inexistant", modules=["fintech", "grc"])
    assert ent.effective_modules() == frozenset({"fintech", "grc"})


def test_effective_modules_never_exceeds_catalogue() -> None:
    ent = _entitlement(tier="full", modules=["bidon", "autre-inconnu"])
    assert ent.effective_modules() <= MODULES


# --------------------------------------------------------------------------
# resolve_box_modules(settings)
# --------------------------------------------------------------------------


def _base_settings_kwargs() -> dict:
    return {
        "POSTGRES_PASSWORD_APP": "x",
        "POSTGRES_PASSWORD_MIGRATIONS": "x",
        "JWT_SECRET": "x" * 32,
    }


def test_resolve_box_modules_returns_none_when_not_enforced() -> None:
    settings = Settings(ENTITLEMENT_ENFORCED=False, **_base_settings_kwargs())
    assert resolve_box_modules(settings) is None


def test_resolve_box_modules_returns_effective_modules_with_valid_license(
    keypair: tuple[str, str],
) -> None:
    priv, pub = keypair
    ent = _entitlement(tier="business", modules=["cyber"])
    token = sign_entitlement(ent, private_key_pem=priv)

    settings = Settings(
        ENTITLEMENT_ENFORCED=True,
        ENTITLEMENT_PUBLIC_KEY=pub,
        ENTITLEMENT_LICENSE_JWT=token,
        **_base_settings_kwargs(),
    )
    resolved = resolve_box_modules(settings)
    assert resolved == frozenset({"erp", "sirh", "bi", "crm", "marketing", "cyber"})


def test_resolve_box_modules_fail_closed_without_license(keypair: tuple[str, str]) -> None:
    _priv, pub = keypair
    settings = Settings(
        ENTITLEMENT_ENFORCED=True,
        ENTITLEMENT_PUBLIC_KEY=pub,
        ENTITLEMENT_LICENSE_JWT="",  # aucune licence déposée
        **_base_settings_kwargs(),
    )
    assert resolve_box_modules(settings) == frozenset()


def test_resolve_box_modules_fail_closed_with_expired_license(keypair: tuple[str, str]) -> None:
    priv, pub = keypair
    now = datetime.now(UTC)
    ent = _entitlement(
        tier="full",
        issued_at=now - timedelta(days=100),
        expires_at=now - timedelta(days=1),
    )
    token = sign_entitlement(ent, private_key_pem=priv)

    settings = Settings(
        ENTITLEMENT_ENFORCED=True,
        ENTITLEMENT_PUBLIC_KEY=pub,
        ENTITLEMENT_LICENSE_JWT=token,
        **_base_settings_kwargs(),
    )
    assert resolve_box_modules(settings) == frozenset()
