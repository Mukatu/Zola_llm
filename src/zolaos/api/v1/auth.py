"""Authentification de production — login par email + mot de passe.

Flux navigateur, cookies **httpOnly** (le JavaScript ne voit jamais les jetons) :

    POST /v1/auth/login    email + mot de passe → access (JWT) + refresh (opaque)
    POST /v1/auth/refresh  refresh token → nouvel access (rotation du refresh)
    POST /v1/auth/logout   révoque le refresh, efface les cookies
    GET  /v1/auth/me       identité courante (pour l'app)

Défenses : bcrypt (mots de passe), rotation des refresh tokens, CSRF double-submit
sur les endpoints mutants, verrou anti-brute-force sur le login, réponse constante
en temps (pas d'énumération des comptes).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate
from zolaos.api.cookies import (
    CSRF_COOKIE,
    CSRF_HEADER,
    clear_auth_cookies,
    set_auth_cookies,
)
from zolaos.core.logging import get_logger
from zolaos.core.rbac import scopes_for_role
from zolaos.core.security import (
    constant_time_equals,
    create_access_token,
    generate_csrf_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import RefreshToken, User
from zolaos.db.session import get_session

_log = get_logger("zolaos.api.v1.auth")

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# Hash bcrypt fixe : comparé quand l'email est inconnu, pour que la réponse
# prenne le même temps qu'un mot de passe réel (anti-énumération par timing).
_DUMMY_HASH = hash_password("zolaos-timing-equalizer")


# ---------------------------------------------------------------------------
# Anti-brute-force : verrou en mémoire par (email, IP). Best-effort, mono-process
# (déploiement Zolabox = une instance) ; remis à zéro au redémarrage. Un backend
# Redis prendrait le relais pour un cluster multi-worker.
# ---------------------------------------------------------------------------
class _LoginThrottle:
    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}

    def _prune(self, key: str, window: float) -> list[float]:
        now = time.monotonic()
        hits = [t for t in self._fails.get(key, []) if now - t < window]
        self._fails[key] = hits
        return hits

    def is_locked(self, key: str, *, settings: Settings) -> bool:
        hits = self._prune(key, settings.AUTH_LOGIN_LOCKOUT_SECONDS)
        return len(hits) >= settings.AUTH_LOGIN_MAX_ATTEMPTS

    def record_failure(self, key: str) -> None:
        self._fails.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._fails.pop(key, None)


_throttle = _LoginThrottle()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    email: str
    display_name: str
    tenant_id: str | None
    country: str
    role: str
    scopes: list[str]


class LoginResponse(BaseModel):
    user: UserOut
    # Rejoué par le client dans l'en-tête X-CSRF-Token sur les requêtes mutantes.
    csrf_token: str


async def _issue_session(
    user: User,
    *,
    response: Response,
    session: AsyncSession,
    settings: Settings,
    user_agent: str | None,
) -> str:
    """Émet access (JWT) + refresh (opaque, stocké haché) + CSRF, et pose les cookies.

    Retourne le jeton CSRF (aussi renvoyé dans le corps pour amorcer le client).
    """
    access = create_access_token(
        str(user.id),
        settings=settings,
        # Les scopes sont une projection du rôle (RBAC) — jamais choisis par le client.
        extra_claims={"scopes": scopes_for_role(user.role)},
    )
    refresh_plain = generate_refresh_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_plain),
        expires_at=datetime.now(tz=UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
        user_agent=(user_agent or "")[:255] or None,
    )
    session.add(refresh_row)
    await session.commit()

    csrf = generate_csrf_token()
    set_auth_cookies(
        response,
        access_token=access,
        refresh_token=refresh_plain,
        csrf_token=csrf,
        settings=settings,
    )
    return csrf


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    email = payload.email.strip().lower()
    key = f"{email}|{_client_ip(request)}"

    if _throttle.is_locked(key, settings=settings):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too_many_attempts",
            headers={"Retry-After": str(settings.AUTH_LOGIN_LOCKOUT_SECONDS)},
        )

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    # Vérifie toujours un hash (réel ou factice) : temps de réponse constant.
    ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok or not user.is_active:
        _throttle.record_failure(key)
        _log.info("auth.login.failed", extra={"email": email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )

    _throttle.reset(key)
    csrf = await _issue_session(
        user,
        response=response,
        session=session,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
    )
    _log.info("auth.login.ok", extra={"user_id": str(user.id)})
    return LoginResponse(
        user=UserOut(
            email=user.email,
            display_name=user.display_name,
            tenant_id=user.tenant_id,
            country=user.country,
            role=user.role,
            scopes=scopes_for_role(user.role),
        ),
        csrf_token=csrf,
    )


def require_csrf(
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
) -> None:
    """Double-submit : l'en-tête doit égaler le cookie CSRF (constant-time)."""
    if not x_csrf_token or not csrf_cookie or not constant_time_equals(x_csrf_token, csrf_cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_failed")


class RefreshResponse(BaseModel):
    csrf_token: str


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    zo_refresh: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> RefreshResponse:
    if not zo_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_refresh")

    token_hash = hash_refresh_token(zo_refresh)
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()

    now = datetime.now(tz=UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        # Jeton inconnu/révoqué/expiré : on nettoie côté client.
        clear_auth_cookies(response, settings=settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh")

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        clear_auth_cookies(response, settings=settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_inactive")

    # Rotation : l'ancien refresh est révoqué, un nouveau est émis.
    row.revoked_at = now
    csrf = await _issue_session(
        user,
        response=response,
        session=session,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
    )
    return RefreshResponse(csrf_token=csrf)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    zo_refresh: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> Response:
    if zo_refresh:
        row = (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_refresh_token(zo_refresh)
                )
            )
        ).scalar_one_or_none()
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(tz=UTC)
            await session.commit()
    clear_auth_cookies(response, settings=settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(principal: Principal = Depends(authenticate)) -> UserOut:
    return UserOut(
        email=principal.email,
        display_name=principal.email,
        tenant_id=principal.tenant_id,
        country=principal.country,
        role=principal.role,
        scopes=list(principal.scopes),
    )
