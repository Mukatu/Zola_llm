"""Authentification HTTP : API key (header) ou JWT Bearer.

Phase 1 : implémentation simple. La création/révocation des clés se fera via
des endpoints d'admin en Phase 4 (GRC).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.core.security import (
    InvalidTokenError,
    decode_access_token,
    hash_api_key,
)
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import ApiKey, User
from zolaos.db.session import get_session

_log = get_logger("zolaos.api.auth")


@dataclass(frozen=True)
class Principal:
    """Identité authentifiée du caller."""

    user_id: uuid.UUID
    email: str
    tenant_id: str | None  # legacy tag string
    country: str
    auth_method: str  # "api_key" | "jwt"
    scopes: tuple[str, ...] = ()
    tenant_uuid: uuid.UUID | None = None  # FK structurée vers core.tenants (Polaris-6)


async def authenticate(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Principal:
    """Tente d'authentifier la requête. Lève 401 sinon."""
    if x_api_key:
        return await _auth_via_api_key(x_api_key, session=session, settings=settings)

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return await _auth_via_jwt(token, session=session, settings=settings)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _auth_via_api_key(
    plain_key: str, *, session: AsyncSession, settings: Settings
) -> Principal:
    pepper = settings.API_KEY_PEPPER.get_secret_value()
    if not pepper:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="api_key_pepper_not_configured",
        )
    key_hash = hash_api_key(plain_key, pepper=pepper)
    stmt = (
        select(ApiKey, User)
        .join(User, ApiKey.user_id == User.id)
        .where(ApiKey.key_hash == key_hash)
        .where(ApiKey.is_active.is_(True))
        .where(User.is_active.is_(True))
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_api_key",
        )
    api_key, user = row
    return Principal(
        user_id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        country=user.country,
        auth_method="api_key",
        scopes=tuple(api_key.scopes or ()),
        tenant_uuid=user.tenant_uuid,
    )


async def _auth_via_jwt(token: str, *, session: AsyncSession, settings: Settings) -> Principal:
    try:
        claims = decode_access_token(token, settings=settings)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid_token: {exc}",
        ) from exc

    user_id = uuid.UUID(claims["sub"])
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_inactive_or_unknown",
        )
    return Principal(
        user_id=user.id,
        email=user.email,
        tenant_id=user.tenant_id,
        country=user.country,
        auth_method="jwt",
        scopes=tuple(claims.get("scopes", []) or ()),
        tenant_uuid=user.tenant_uuid,
    )
