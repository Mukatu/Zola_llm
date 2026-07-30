"""Collecte d'usage inter-box (facturation, déploiement hybride).

Côté **box** : `collect_local_usage` agrège le `core.usage_daily` local (les totaux
du jour, tous tenants locaux confondus) pour les remonter au Cortex par le tunnel.
Côté **cortex** : `ingest_reported_usage` persiste un rapport reçu **sous l'identité
authentifiée de la box** (jamais le tenant du payload) — `set_usage_durable` écrase
les totaux du jour (idempotent).

Les deux ouvrent leur propre session (appelés hors contexte de requête, depuis la
boucle du tunnel).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from zolaos.billing.ledger import set_usage_durable
from zolaos.core.logging import get_logger
from zolaos.db.models import UsageDaily
from zolaos.db.session import get_session_factory

_log = get_logger("zolaos.billing.collector")


async def collect_local_usage(days: int = 2) -> list[dict[str, int | str]]:
    """Totaux d'usage locaux des `days` derniers jours → `[{day, requests, tokens}]`.

    `day` au format `YYYYMMDD` (compatible avec le rapport tunnel). On remonte 2 jours
    par défaut : le jour courant + la veille (pour les requêtes tardives d'hier)."""
    since = datetime.now(UTC).date() - timedelta(days=max(0, days - 1))
    async with get_session_factory()() as session:
        rows = (
            await session.execute(
                select(
                    UsageDaily.day,
                    func.coalesce(func.sum(UsageDaily.requests), 0),
                    func.coalesce(func.sum(UsageDaily.tokens), 0),
                )
                .where(UsageDaily.day >= since)
                .group_by(UsageDaily.day)
            )
        ).all()
    return [
        {"day": d.strftime("%Y%m%d"), "requests": int(req), "tokens": int(tok)}
        for d, req, tok in rows
    ]


async def ingest_reported_usage(tenant_id: str, *, day: str, requests: int, tokens: int) -> None:
    """Persiste un rapport d'usage reçu d'une box, sous `tenant_id` (identité box).

    `day` est `YYYYMMDD`. Écrase les totaux du jour (idempotent). Ouvre sa session."""
    try:
        parsed = datetime.strptime(day, "%Y%m%d").replace(tzinfo=UTC).date()
    except (ValueError, TypeError):
        _log.warning("usage.report_bad_day", tenant_id=tenant_id, day=str(day))
        return
    if not isinstance(requests, int) or not isinstance(tokens, int) or requests < 0 or tokens < 0:
        _log.warning("usage.report_bad_values", tenant_id=tenant_id)
        return
    async with get_session_factory()() as session:
        await set_usage_durable(
            session, tenant_id=tenant_id, day=parsed, requests=requests, tokens=tokens
        )
        await session.commit()
    _log.info("usage.report_ingested", tenant_id=tenant_id, day=day, requests=requests)
