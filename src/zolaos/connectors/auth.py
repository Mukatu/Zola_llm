"""Authentification pluggable pour le Connector Framework (V2.2 §2.4).

Stratégies : API key, OAuth2 (client credentials), Basic, certificat client,
IP allowlist. Secrets toujours via `SecretStr` (directive §5.3 : jamais en
clair). Les stratégies HTTP exposent :

- `await prepare()`   : préparation asynchrone éventuelle (ex: fetch token OAuth2)
- `apply_headers(h)`  : injecte les en-têtes d'auth dans `h`
- `httpx_kwargs()`    : kwargs additionnels pour `httpx` (ex: cert client)

`IPAllowlist` est un garde-fou d'**entrée** (webhook), pas une auth sortante.
"""

from __future__ import annotations

import base64
import time
from abc import ABC, abstractmethod
from ipaddress import ip_address, ip_network
from typing import Any

import httpx
from pydantic import SecretStr

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.connectors.auth")


class AuthStrategy(ABC):
    """Interface commune des stratégies d'authentification sortantes."""

    async def prepare(self) -> None:
        """Préparation asynchrone (no-op par défaut)."""
        return None

    @abstractmethod
    def apply_headers(self, headers: dict[str, str]) -> None:
        """Injecte les en-têtes d'authentification (mutation en place)."""

    def httpx_kwargs(self) -> dict[str, Any]:
        """Kwargs additionnels pour le client httpx (cert, verify…)."""
        return {}


class NoAuth(AuthStrategy):
    """Aucune authentification (systèmes ouverts / tests)."""

    def apply_headers(self, headers: dict[str, str]) -> None:
        return None


class ApiKeyAuth(AuthStrategy):
    """Clé d'API dans un en-tête (par défaut `X-API-Key`)."""

    def __init__(self, key: SecretStr, *, header_name: str = "X-API-Key") -> None:
        self._key = key
        self._header = header_name

    def apply_headers(self, headers: dict[str, str]) -> None:
        headers[self._header] = self._key.get_secret_value()


class BasicAuth(AuthStrategy):
    """Authentification HTTP Basic."""

    def __init__(self, username: str, password: SecretStr) -> None:
        self._username = username
        self._password = password

    def apply_headers(self, headers: dict[str, str]) -> None:
        raw = f"{self._username}:{self._password.get_secret_value()}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")


class OAuth2Auth(AuthStrategy):
    """OAuth2 *client credentials* avec cache de token (refresh sur expiration)."""

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: SecretStr,
        scope: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def prepare(self) -> None:
        # Refresh si pas de token ou expiré (marge de 30 s).
        if self._token is not None and time.monotonic() < self._expires_at - 30:
            return
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret.get_secret_value(),
        }
        if self._scope:
            data["scope"] = self._scope
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._token_url, data=data)
        if r.status_code >= 400:
            from zolaos.connectors.base import ConnectorAuthError

            raise ConnectorAuthError(f"OAuth2 token refusé ({r.status_code}): {r.text[:200]}")
        payload = r.json()
        self._token = payload["access_token"]
        self._expires_at = time.monotonic() + float(payload.get("expires_in", 3600))
        _log.info("connectors.auth.oauth2_token_refreshed", expires_in=payload.get("expires_in"))

    def apply_headers(self, headers: dict[str, str]) -> None:
        if self._token is None:
            from zolaos.connectors.base import ConnectorAuthError

            raise ConnectorAuthError("OAuth2 : token non préparé (appeler prepare() d'abord)")
        headers["Authorization"] = f"Bearer {self._token}"


class CertificateAuth(AuthStrategy):
    """Certificat client TLS (mutual TLS). N'ajoute pas d'en-tête."""

    def __init__(self, cert_path: str, key_path: str | None = None) -> None:
        self._cert = cert_path if key_path is None else (cert_path, key_path)

    def apply_headers(self, headers: dict[str, str]) -> None:
        return None

    def httpx_kwargs(self) -> dict[str, Any]:
        return {"cert": self._cert}


class IPAllowlist:
    """Garde-fou d'entrée : autorise uniquement certaines IP/plages (webhook).

    N'est PAS une `AuthStrategy` sortante : c'est un contrôle d'accès entrant.
    """

    def __init__(self, allowed: list[str]) -> None:
        self._networks = [ip_network(c, strict=False) for c in allowed]

    def is_allowed(self, ip: str) -> bool:
        try:
            addr = ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in self._networks)
