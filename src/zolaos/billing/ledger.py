"""Grand livre d'usage durable — upsert par tenant/jour (base de facturation).

Écrit dans `core.usage_daily` (persistant), en complément des compteurs Redis
éphémères du quota. Un upsert atomique (`INSERT … ON CONFLICT`) incrémente la
ligne du jour : +1 requête, +tokens. Appelé au mieux (fail-open) par le metering
lorsque `BILLING_LEDGER_ENABLED`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.models import UsageDaily


async def record_usage_durable(
    session: AsyncSession,
    *,
    tenant_id: str,
    day: date,
    requests: int = 1,
    tokens: int = 0,
) -> None:
    """Incrémente (upsert) l'usage durable du jour pour `tenant_id`.

    Idempotent au sens transactionnel : deux requêtes concurrentes du même tenant
    s'additionnent grâce à `ON CONFLICT DO UPDATE` (pas de lost update)."""
    stmt = pg_insert(UsageDaily).values(
        tenant_id=tenant_id, day=day, requests=requests, tokens=tokens
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UsageDaily.tenant_id, UsageDaily.day],
        set_={
            "requests": UsageDaily.requests + requests,
            "tokens": UsageDaily.tokens + tokens,
        },
    )
    await session.execute(stmt)
