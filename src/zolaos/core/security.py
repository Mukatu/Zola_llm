"""Primitives de sécurité : hashing API key + JWT + mots de passe."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from zolaos.core.settings import Settings

# bcrypt limite l'entrée utile à 72 octets. On pré-hash avec SHA-256 pour
# accepter n'importe quelle longueur de manière déterministe et sûre.
_BCRYPT_ROUNDS = 12


def _prepare_password(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(_prepare_password(password), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare_password(password), password_hash.encode("ascii"))
    except ValueError:
        return False


# ===== API keys =====
# Format : `zlk_<base64url>` (zlk = ZolaOS Live Key). Hash HMAC-SHA256 avec pepper.
API_KEY_PREFIX = "zlk_"
API_KEY_LENGTH_BYTES = 32


def generate_api_key() -> tuple[str, str, str]:
    """Retourne (key_clair, key_prefix, key_hash). Le clair n'est PAS stocké."""
    body = secrets.token_urlsafe(API_KEY_LENGTH_BYTES)
    plain = f"{API_KEY_PREFIX}{body}"
    return plain, plain[:12], _hash_api_key_unsalted(plain, pepper="placeholder")


def hash_api_key(plain: str, *, pepper: str) -> str:
    return _hash_api_key_unsalted(plain, pepper=pepper)


def verify_api_key(plain: str, stored_hash: str, *, pepper: str) -> bool:
    return hmac.compare_digest(_hash_api_key_unsalted(plain, pepper=pepper), stored_hash)


def _hash_api_key_unsalted(plain: str, *, pepper: str) -> str:
    """HMAC-SHA256(pepper, plain). On évite bcrypt ici (constant-time + hashable index)."""
    return hmac.new(pepper.encode("utf-8"), plain.encode("utf-8"), hashlib.sha256).hexdigest()


# ===== JWT =====
def create_access_token(
    subject: str,
    *,
    settings: Settings,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
        "iss": settings.OTEL_SERVICE_NAME,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    """Décode + valide. Lève `InvalidTokenError` sur token invalide/expiré."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


class InvalidTokenError(RuntimeError):
    pass
