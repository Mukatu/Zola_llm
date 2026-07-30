"""Cockpit cabinet — usage & facturation par tenant (Zolacortex).

Réservé au profil **cortex** et au rôle **admin**. Agrège le grand livre d'usage
durable (`core.usage_daily`) sur une période mensuelle, rapproche chaque tenant de
`core.tenants` (nom) et de sa licence (tier), puis applique le **barème** (mécanisme
`zolaos.billing.pricing` ; les prix viennent de la config, jamais inventés).

Lecture seule. Portée : couvre l'usage enregistré contre la base de ce déploiement ;
la collecte inter-box (box → cortex par tunnel) reste un suivi.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import require_admin
from zolaos.billing import compute_bill, load_pricing
from zolaos.core.profiles import require_cortex
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import LicenseGrant, Tenant, UsageDaily
from zolaos.db.session import get_session

router = APIRouter(
    prefix="/v1/cortex/billing",
    tags=["cortex", "billing"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)


def _month_bounds(period: str | None) -> tuple[str, date, date]:
    """(période normalisée YYYY-MM, premier jour, premier jour du mois suivant)."""
    now = datetime.now(UTC)
    if period is None:
        year, month = now.year, now.month
    else:
        try:
            year, month = (int(x) for x in period.split("-", 1))
            date(year, month, 1)  # valide
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="invalid_period (attendu YYYY-MM)") from exc
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return (f"{year:04d}-{month:02d}", start, end)


class BillingRow(BaseModel):
    tenant_id: str
    name: str | None  # nom si le tenant_id correspond à un core.tenants, sinon None
    tier: str | None
    requests: int
    tokens: int
    cost: dict[str, Any]  # cf. zolaos.billing.pricing.compute_bill


class BillingResponse(BaseModel):
    period: str
    currency: str
    rows: list[BillingRow]
    total_requests: int
    total_tokens: int
    total_cost: int


@router.get("/pricing", summary="Barème de facturation courant")
async def get_pricing(
    settings: Settings = Depends(get_settings),
) -> dict[str, dict[str, Any]]:
    """Barème par tier tel que configuré (défauts à zéro si non défini)."""
    return load_pricing(settings)


@router.get("", response_model=BillingResponse, summary="Usage & facturation par tenant")
async def get_billing(
    period: str | None = Query(default=None, description="Mois YYYY-MM (défaut : mois courant)"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> BillingResponse:
    period_label, start, end = _month_bounds(period)
    pricing = load_pricing(settings)

    # 1. Usage agrégé du mois par tenant.
    usage_rows = (
        await session.execute(
            select(
                UsageDaily.tenant_id,
                func.coalesce(func.sum(UsageDaily.requests), 0),
                func.coalesce(func.sum(UsageDaily.tokens), 0),
            )
            .where(UsageDaily.day >= start, UsageDaily.day < end)
            .group_by(UsageDaily.tenant_id)
        )
    ).all()

    # 2. Résolution nom + tier pour les tenant_id qui sont des UUID de core.tenants.
    tenants = (
        (await session.execute(select(Tenant).where(Tenant.tenant_type == "client")))
        .scalars()
        .all()
    )
    name_by_id = {str(t.id): t.name for t in tenants}
    ids = [t.id for t in tenants]
    tier_by_id: dict[str, str] = {}
    if ids:
        grant_rows = (
            (
                await session.execute(
                    select(LicenseGrant)
                    .where(LicenseGrant.tenant_id.in_(ids), LicenseGrant.revoked_at.is_(None))
                    .order_by(LicenseGrant.tenant_id, LicenseGrant.created_at.desc())
                    .distinct(LicenseGrant.tenant_id)
                )
            )
            .scalars()
            .all()
        )
        tier_by_id = {str(g.tenant_id): g.tier for g in grant_rows}

    rows: list[BillingRow] = []
    total_requests = total_tokens = total_cost = 0
    currency = "XAF"
    for tenant_id, req, tok in usage_rows:
        tier = tier_by_id.get(tenant_id)
        cost = compute_bill(tier, requests=int(req), tokens=int(tok), pricing=pricing)
        currency = cost["currency"]
        rows.append(
            BillingRow(
                tenant_id=tenant_id,
                name=name_by_id.get(tenant_id),
                tier=tier,
                requests=int(req),
                tokens=int(tok),
                cost=cost,
            )
        )
        total_requests += int(req)
        total_tokens += int(tok)
        total_cost += int(cost["total"])

    # Remonte les plus gros postes (coût, puis volume) en tête.
    rows.sort(key=lambda r: (r.cost["total"], r.requests), reverse=True)

    return BillingResponse(
        period=period_label,
        currency=currency,
        rows=rows,
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost=total_cost,
    )
