"""Cookies d'authentification (login navigateur).

Trois cookies sont posés à la connexion :

- ``zo_access``  : access token JWT court. **httpOnly** → invisible au JavaScript,
  donc invulnérable au vol par XSS. Envoyé sur tout le site (``Path=/``).
- ``zo_refresh`` : refresh token opaque, **httpOnly**, cantonné à ``/v1/auth`` :
  le navigateur ne l'expose qu'aux endpoints de refresh/logout.
- ``zo_csrf``    : jeton CSRF **lisible** par le JS (pas httpOnly). Le client le
  rejoue dans l'en-tête ``X-CSRF-Token`` (double-submit). Combiné à
  ``SameSite=lax``, il neutralise les requêtes forgées cross-site.

``Secure`` (HTTPS obligatoire) est forcé hors dev — voir ``cookie_secure``.
"""

from __future__ import annotations

from fastapi import Response

from zolaos.core.settings import Settings

ACCESS_COOKIE = "zo_access"
REFRESH_COOKIE = "zo_refresh"
CSRF_COOKIE = "zo_csrf"
CSRF_HEADER = "X-CSRF-Token"

# Le refresh cookie n'est renvoyé qu'aux endpoints d'auth (réduit l'exposition).
_REFRESH_PATH = "/v1/auth"


def cookie_secure(settings: Settings) -> bool:
    """HTTPS-only pour les cookies. Explicite si défini, sinon auto (True hors dev)."""
    if settings.AUTH_COOKIE_SECURE is not None:
        return settings.AUTH_COOKIE_SECURE
    return settings.APP_ENV != "dev"


def _domain(settings: Settings) -> str | None:
    return settings.AUTH_COOKIE_DOMAIN or None


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    secure = cookie_secure(settings)
    samesite = settings.AUTH_COOKIE_SAMESITE
    domain = _domain(settings)
    access_max_age = settings.JWT_EXPIRE_MINUTES * 60
    refresh_max_age = settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 3600

    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path=_REFRESH_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_max_age,
        httponly=False,  # lisible par le JS : c'est le principe du double-submit
        secure=secure,
        samesite=samesite,
        domain=domain,
        path="/",
    )


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    domain = _domain(settings)
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH, domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
