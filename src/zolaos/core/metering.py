"""Metering d'usage + quotas par clé API pour le moteur souverain.

Phase 1 : compteurs Redis par jour (requêtes + tokens) par `key_id`, et un
quota **global** par défaut (`ENGINE_DAILY_REQUEST_QUOTA`). Le quota par clé
fin (config individuelle par `ApiKey`, Phase 4 GRC) pourra se brancher plus
tard en surchargeant simplement la valeur passée à `enforce_quota` — la
signature ne change pas.

Réutilise le patron de `zolaos.core.rate_limit` (compteur fixe Redis + TTL),
mais sur une fenêtre **jour** (`YYYYMMDD`) plutôt que minute, et sans jugement
d'admission propre : ce module ne fait qu'incrémenter/lire/vérifier, la
décision HTTP (429) est prise par la dépendance `require_quota`.

NB : `Settings.ENGINE_DAILY_REQUEST_QUOTA` / `ENGINE_METERING_ENABLED` ne sont
*pas encore* déclarés dans `zolaos.core.settings` (ce lot ne modifie pas
`settings.py`) — `require_quota` lit ces champs via `getattr(..., default)`
pour rester fonctionnel (metering activé, quota illimité) avant le câblage de
l'orchestrateur, et bascule sans changement de code une fois les champs
ajoutés.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import Depends, HTTPException, status

from zolaos.api.auth import Principal, authenticate
from zolaos.core.logging import get_logger
from zolaos.core.rate_limit import make_redis_client
from zolaos.core.settings import Settings, get_settings

_log = get_logger("zolaos.core.metering")

# TTL des compteurs journaliers : assez large pour couvrir un mois de
# reporting/facturation avec marge, sans accumuler indéfiniment dans Redis.
USAGE_TTL_SECONDS = 40 * 24 * 3600


class RedisLike(Protocol):
    """Surface Redis minimale utilisée ici (incr/expire/get async).

    Permet de faire tourner les tests sans Redis réel (faux client
    in-memory) tout en restant compatible avec `redis.asyncio.Redis`.
    """

    async def incr(self, name: str, amount: int = 1) -> Any: ...
    async def expire(self, name: str, time: int) -> Any: ...
    async def get(self, name: str) -> Any: ...


class QuotaExceeded(Exception):
    """Levée quand le quota de requêtes quotidien d'une clé est atteint."""


def _today(day: str | None = None) -> str:
    """Jour courant en `YYYYMMDD` (UTC), ou `day` si fourni (tests/rejeu)."""
    return day or datetime.now(UTC).strftime("%Y%m%d")


def _usage_key(key_id: str, day: str, metric: str) -> str:
    """Clé Redis d'un compteur d'usage : ``usage:{key_id}:{YYYYMMDD}:{metric}``."""
    return f"usage:{key_id}:{day}:{metric}"


async def record_usage(
    redis: RedisLike,
    *,
    key_id: str,
    tokens: int = 0,
    day: str | None = None,
) -> None:
    """Incrémente les compteurs d'usage du jour pour `key_id` (+1 requête, +`tokens`)."""
    d = _today(day)
    req_key = _usage_key(key_id, d, "req")
    await redis.incr(req_key, 1)
    await redis.expire(req_key, USAGE_TTL_SECONDS)

    if tokens:
        tok_key = _usage_key(key_id, d, "tok")
        await redis.incr(tok_key, tokens)
        await redis.expire(tok_key, USAGE_TTL_SECONDS)


async def get_usage(redis: RedisLike, *, key_id: str, day: str) -> dict[str, int]:
    """Lit `{"requests": ..., "tokens": ...}` pour `key_id` au jour `day` (`YYYYMMDD`)."""
    req_raw = await redis.get(_usage_key(key_id, day, "req"))
    tok_raw = await redis.get(_usage_key(key_id, day, "tok"))
    return {
        "requests": int(req_raw) if req_raw is not None else 0,
        "tokens": int(tok_raw) if tok_raw is not None else 0,
    }


async def enforce_quota(
    redis: RedisLike,
    *,
    key_id: str,
    daily_request_quota: int | None,
) -> None:
    """Lève `QuotaExceeded` si le compteur de requêtes du jour atteint le quota.

    `daily_request_quota` est `None` (ou `0`) → illimité, ne lève jamais.
    """
    if not daily_request_quota:
        return

    day = _today()
    raw = await redis.get(_usage_key(key_id, day, "req"))
    count = int(raw) if raw is not None else 0
    if count >= daily_request_quota:
        raise QuotaExceeded(
            f"daily_request_quota_exceeded: key_id={key_id} quota={daily_request_quota}"
        )


# --- Dépendance FastAPI --------------------------------------------------

_redis_singleton: RedisLike | None = None


def get_metering_redis(settings: Settings = Depends(get_settings)) -> RedisLike:
    """Client Redis partagé pour le metering (singleton process, cf. `make_redis_client`).

    Un seul client est construit paresseusement puis réutilisé — évite de
    recréer une pool de connexions à chaque requête, sans dépendre du cycle
    de vie de l'app (`main.py` n'est pas modifié par ce lot).
    """
    global _redis_singleton
    if _redis_singleton is None:
        _redis_singleton = make_redis_client(settings)
    return _redis_singleton


async def require_quota(
    principal: Principal = Depends(authenticate),
    settings: Settings = Depends(get_settings),
    redis: RedisLike = Depends(get_metering_redis),
) -> Principal:
    """Dépendance FastAPI : applique le quota du jour puis enregistre l'usage.

    À poser sur les routes du moteur (`/v1/query`, `/v1/chat/completions`, …),
    en général à la place de (ou en plus de) `Depends(authenticate)` — elle
    authentifie déjà via `authenticate`. Ordre : `enforce_quota` d'abord (429
    si dépassé, la requête n'est PAS comptée), puis `record_usage` (+1
    requête) seulement si elle est admise.

    Phase 1 : quota **global** (même valeur pour toutes les clés) lu depuis
    `Settings.ENGINE_DAILY_REQUEST_QUOTA` (0/absent = illimité) ; le quota
    par-clé fin viendra plus tard sans changer cette dépendance.
    """
    metering_enabled = getattr(settings, "ENGINE_METERING_ENABLED", True)
    if not metering_enabled:
        return principal

    key_id = str(principal.user_id)
    quota = getattr(settings, "ENGINE_DAILY_REQUEST_QUOTA", 0) or None

    try:
        await enforce_quota(redis, key_id=key_id, daily_request_quota=quota)
    except QuotaExceeded as exc:
        _log.warning("quota_exceeded", key_id=key_id, quota=quota)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="quota_exceeded",
        ) from exc
    except Exception as exc:  # store indisponible → FAIL-OPEN : ne jamais bloquer le moteur
        _log.warning("metering.enforce_unavailable", error=str(exc))
        return principal

    try:
        await record_usage(redis, key_id=key_id)
    except Exception as exc:  # idem : la panne du compteur ne doit pas 500 une requête admise
        _log.warning("metering.record_unavailable", error=str(exc))
    return principal
