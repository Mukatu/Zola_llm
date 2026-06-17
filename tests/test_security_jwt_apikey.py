"""Tests unitaires JWT + API key (sans DB)."""

from __future__ import annotations

import pytest

from zolaos.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from zolaos.core.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        JWT_SECRET="x" * 64,  # noqa: S106
        API_KEY_PEPPER="y" * 64,  # noqa: S106
        JWT_EXPIRE_MINUTES=15,
    )


def test_password_hash_and_verify() -> None:
    h = hash_password("super_secret")
    assert verify_password("super_secret", h)
    assert not verify_password("wrong", h)


def test_api_key_hmac_is_deterministic(settings: Settings) -> None:
    pepper = settings.API_KEY_PEPPER.get_secret_value()
    h1 = hash_api_key("zlk_abc", pepper=pepper)
    h2 = hash_api_key("zlk_abc", pepper=pepper)
    assert h1 == h2
    assert verify_api_key("zlk_abc", h1, pepper=pepper)
    assert not verify_api_key("zlk_xyz", h1, pepper=pepper)


def test_jwt_roundtrip(settings: Settings) -> None:
    token = create_access_token("user-123", settings=settings)
    claims = decode_access_token(token, settings=settings)
    assert claims["sub"] == "user-123"
    assert "exp" in claims


def test_jwt_invalid_signature_rejected(settings: Settings) -> None:
    token = create_access_token("user-123", settings=settings)
    other_settings = Settings(JWT_SECRET="z" * 64, API_KEY_PEPPER="y" * 64)  # noqa: S106
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings=other_settings)
