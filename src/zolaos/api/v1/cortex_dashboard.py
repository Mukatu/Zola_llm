"""Cockpit cabinet — tableau de bord de pilotage (KPI transverses).

Le **capstone** : une synthèse en lecture sur toute la chaîne de valeur —
commercial (pipeline pondéré), production (missions actives, taux d'occupation),
finance (WIP, honoraires facturés/encaissés, créances) et rentabilité (marge). Ne
crée rien : agrège `opportunities`, `missions`, `time_entries` et `invoices` sur un
mois, en réutilisant les moteurs déterministes (`crm`, `psa`) déjà éprouvés.

Réservé profil **cortex** + rôle **admin**. Lecture seule.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import require_admin
from zolaos.core.profiles import require_cortex
from zolaos.core.settings import Settings, get_settings
from zolaos.crm import summarize_pipeline
from zolaos.db.models import Invoice, Mission, Opportunity, TimeEntry
from zolaos.db.session import get_session
from zolaos.psa import compute_utilization, entry_amounts

router = APIRouter(
    prefix="/v1/cortex/dashboard",
    tags=["cortex", "dashboard"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)


def _business_days(year: int, month: int) -> int:
    days = monthrange(year, month)[1]
    return sum(1 for d in range(1, days + 1) if date(year, month, d).weekday() < 5)


class Commercial(BaseModel):
    open_count: int
    open_amount: int
    open_weighted: int  # prévision pondérée du pipeline
    win_rate: int | None


class Production(BaseModel):
    active_missions: int
    active_consultants: int
    worked_hours: float
    billable_hours: float
    occupation_pct: int | None


class Finance(BaseModel):
    honoraires_period: int  # valeur facturable produite sur le mois
    cost_period: int
    margin_period: int
    margin_pct: int | None
    wip: int  # approuvé non facturé (encours à facturer)
    invoiced_period: int  # facturé (émis) sur le mois
    collected_period: int  # encaissé sur le mois
    outstanding: int  # créances émises non payées (snapshot)


class DashboardResponse(BaseModel):
    period: str
    currency: str
    commercial: Commercial
    production: Production
    finance: Finance


@router.get("", response_model=DashboardResponse, summary="KPI de pilotage du cabinet")
async def dashboard(
    period: str | None = Query(default=None, description="Mois YYYY-MM (défaut : mois courant)"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DashboardResponse:
    now = datetime.now(UTC)
    if period is None:
        year, month = now.year, now.month
    else:
        try:
            year, month = (int(x) for x in period.split("-", 1))
            date(year, month, 1)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="invalid_period (YYYY-MM)") from exc
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    # --- Commercial : pipeline pondéré (toutes opportunités) ---
    opp_rows = (await session.execute(select(Opportunity))).scalars().all()
    pipe = summarize_pipeline(
        [
            {"stage": o.stage, "amount_estimate": o.amount_estimate, "probability": o.probability}
            for o in opp_rows
        ]
    )

    # --- Production : missions actives + temps du mois ---
    active_missions = (
        await session.execute(
            select(func.count()).select_from(Mission).where(Mission.status == "active")
        )
    ).scalar_one()

    period_entries = (
        (
            await session.execute(
                select(TimeEntry).where(
                    TimeEntry.entry_date >= start,
                    TimeEntry.entry_date < end,
                    TimeEntry.status != "rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    worked_minutes = billable_minutes = honoraires = cost = 0
    consultants: set[Any] = set()
    for e in period_entries:
        amt = entry_amounts(
            minutes=e.minutes, bill_rate=e.bill_rate, cost_rate=e.cost_rate, billable=e.billable
        )
        worked_minutes += e.minutes
        cost += amt["cost"]
        honoraires += amt["honoraires"]
        consultants.add(e.consultant_user_id)
        if e.billable:
            billable_minutes += e.minutes

    available = round(
        len(consultants) * _business_days(year, month) * settings.PSA_HOURS_PER_DAY * 60
    )
    util = compute_utilization(
        worked_minutes=worked_minutes,
        billable_minutes=billable_minutes,
        available_minutes=available,
    )

    # --- Finance : WIP + factures du mois + créances ---
    wip = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(func.round(TimeEntry.minutes * TimeEntry.bill_rate / 60.0)), 0
                )
            ).where(
                TimeEntry.status == "approved",
                TimeEntry.billable.is_(True),
                TimeEntry.invoice_id.is_(None),
            )
        )
    ).scalar_one()

    invoiced_period = (
        await session.execute(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(
                Invoice.issued_date >= start,
                Invoice.issued_date < end,
                Invoice.status.in_(("issued", "paid")),
            )
        )
    ).scalar_one()
    collected_period = (
        await session.execute(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(
                Invoice.paid_date >= start,
                Invoice.paid_date < end,
                Invoice.status == "paid",
            )
        )
    ).scalar_one()
    outstanding = (
        await session.execute(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.status == "issued")
        )
    ).scalar_one()

    margin = honoraires - cost
    margin_pct = round(margin / honoraires * 100) if honoraires else None

    return DashboardResponse(
        period=f"{year:04d}-{month:02d}",
        currency="XAF",
        commercial=Commercial(
            open_count=pipe["open_count"],
            open_amount=pipe["open_amount"],
            open_weighted=pipe["open_weighted"],
            win_rate=pipe["win_rate"],
        ),
        production=Production(
            active_missions=int(active_missions),
            active_consultants=len(consultants),
            worked_hours=round(worked_minutes / 60, 2),
            billable_hours=round(billable_minutes / 60, 2),
            occupation_pct=util["occupation_pct"],
        ),
        finance=Finance(
            honoraires_period=honoraires,
            cost_period=cost,
            margin_period=margin,
            margin_pct=margin_pct,
            wip=int(wip),
            invoiced_period=int(invoiced_period),
            collected_period=int(collected_period),
            outstanding=int(outstanding),
        ),
    )
