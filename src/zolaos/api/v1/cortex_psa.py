"""Cockpit cabinet — PSA : feuilles de temps, économie de mission, taux d'occupation.

Réservé au profil **cortex**. Socle du PSA : les consultants saisissent leur temps
sur les missions (draft → submitted → approved) ; on en dérive, de façon
**déterministe**, les honoraires/coût/marge par mission et le taux d'occupation par
consultant. Les taux sont **figés à la saisie** (barème `PSA_RATE_CARD_JSON`).

Sécurité : un consultant saisit/soumet SON temps ; l'approbation et les vues
agrégées (économie, occupation) sont réservées au rôle admin. Mutations sous CSRF.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import Mission, Tenant, TimeEntry, User
from zolaos.db.session import get_session
from zolaos.psa import (
    compute_engagement_economics,
    compute_utilization,
    entry_amounts,
    load_rate_card,
    resolve_rates,
)
from zolaos.psa.time_assist import suggest_time_entries

_log = get_logger("zolaos.api.v1.cortex_psa")

router = APIRouter(
    prefix="/v1/cortex/psa", tags=["cortex", "psa"], dependencies=[Depends(require_cortex)]
)

_OWNER_EDITABLE = "draft"


# ---------------------------------------------------------------------------
# Feuilles de temps
# ---------------------------------------------------------------------------
class TimeEntryOut(BaseModel):
    id: uuid.UUID
    consultant_user_id: uuid.UUID
    mission_id: uuid.UUID
    entry_date: date
    minutes: int
    billable: bool
    activity: str
    status: str
    bill_rate: int
    cost_rate: int
    honoraires: int  # calculé (0 si non facturable)
    cost: int


def _to_out(e: TimeEntry) -> TimeEntryOut:
    amt = entry_amounts(
        minutes=e.minutes, bill_rate=e.bill_rate, cost_rate=e.cost_rate, billable=e.billable
    )
    return TimeEntryOut(
        id=e.id,
        consultant_user_id=e.consultant_user_id,
        mission_id=e.mission_id,
        entry_date=e.entry_date,
        minutes=e.minutes,
        billable=e.billable,
        activity=e.activity,
        status=e.status,
        bill_rate=e.bill_rate,
        cost_rate=e.cost_rate,
        honoraires=amt["honoraires"],
        cost=amt["cost"],
    )


class CreateTimeEntry(BaseModel):
    mission_id: uuid.UUID
    entry_date: date
    minutes: int = Field(gt=0, le=24 * 60)
    billable: bool = True
    activity: str = Field(default="", max_length=1000)


@router.post("/time-entries", response_model=TimeEntryOut, status_code=status.HTTP_201_CREATED)
async def create_time_entry(
    payload: CreateTimeEntry,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> TimeEntryOut:
    """Saisit du temps pour le consultant courant. Le taux est figé selon son grade."""
    mission = await session.get(Mission, payload.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission_not_found")

    user = await session.get(User, principal.user_id)
    grade = user.grade if user is not None else None
    bill_rate, cost_rate = resolve_rates(grade, load_rate_card(settings))

    entry = TimeEntry(
        consultant_user_id=principal.user_id,
        mission_id=payload.mission_id,
        entry_date=payload.entry_date,
        minutes=payload.minutes,
        billable=payload.billable,
        activity=payload.activity,
        status="draft",
        bill_rate=bill_rate,
        cost_rate=cost_rate,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    _log.info("psa.time_entry.created", extra={"entry_id": str(entry.id)})
    return _to_out(entry)


# ---------------------------------------------------------------------------
# Saisie assistée (IA) — récit libre → propositions de lignes (rien n'est créé)
# ---------------------------------------------------------------------------
class AssistTimeRequest(BaseModel):
    narrative: str = Field(min_length=3, max_length=4000)
    week_start: date | None = Field(
        default=None, description="Lundi de référence pour résoudre « lundi/mardi… »"
    )


class TimeSuggestionOut(BaseModel):
    entry_date: date | None
    minutes: int
    hours: float
    activity: str
    billable: bool
    mission_id: uuid.UUID | None
    mission_label: str | None


class AssistTimeResponse(BaseModel):
    status: str  # suggested | unavailable
    suggestions: list[TimeSuggestionOut]


@router.post("/time-entries/assist", response_model=AssistTimeResponse)
async def assist_time_entries(
    payload: AssistTimeRequest,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> AssistTimeResponse:
    """Extrait des **propositions** de lignes de temps du récit libre du consultant
    (le LLM structure, il n'invente ni durée ni activité absente du récit ; mission
    choisie parmi celles du consultant). **Ne crée rien** : le consultant relit,
    corrige et valide chaque ligne avant de la saisir (les taux/montants restent
    déterministes, figés à la création réelle). `status` : `suggested` (liste éventuelle-
    ment vide) ou `unavailable` (LLM indisponible)."""
    rows = (
        await session.execute(
            select(Mission, Tenant.name)
            .join(Tenant, Tenant.id == Mission.client_tenant_id, isouter=True)
            .where(Mission.consultant_user_id == principal.user_id)
            .order_by(Mission.started_at.desc())
            .limit(50)
        )
    ).all()
    missions = [
        {"id": str(m.id), "label": f"{m.offre or 'mission'} — {name or 'client'}"}
        for m, name in rows
    ]

    outcome = await suggest_time_entries(
        settings,
        narrative=payload.narrative,
        week_start=payload.week_start,
        missions=missions,
    )
    _log.info(
        "psa.time_entry.assisted",
        extra={"status": outcome.status, "count": len(outcome.suggestions)},
    )
    return AssistTimeResponse(
        status=outcome.status,
        suggestions=[
            TimeSuggestionOut(
                entry_date=date.fromisoformat(s.entry_date) if s.entry_date else None,
                minutes=s.minutes,
                hours=round(s.minutes / 60, 2),
                activity=s.activity,
                billable=s.billable,
                mission_id=uuid.UUID(s.mission_id) if s.mission_id else None,
                mission_label=s.mission_label,
            )
            for s in outcome.suggestions
        ],
    )


@router.get("/time-entries", response_model=list[TimeEntryOut])
async def list_time_entries(
    mission_id: uuid.UUID | None = Query(default=None),
    mine: bool = Query(default=True, description="Limiter à mes saisies (défaut)"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> list[TimeEntryOut]:
    stmt = select(TimeEntry).order_by(TimeEntry.entry_date.desc()).limit(limit)
    if mine:
        stmt = stmt.where(TimeEntry.consultant_user_id == principal.user_id)
    if mission_id is not None:
        stmt = stmt.where(TimeEntry.mission_id == mission_id)
    if status_filter is not None:
        stmt = stmt.where(TimeEntry.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(e) for e in rows]


class UpdateTimeEntry(BaseModel):
    # Édition (propriétaire, draft uniquement).
    minutes: int | None = Field(default=None, gt=0, le=24 * 60)
    billable: bool | None = None
    activity: str | None = Field(default=None, max_length=1000)
    # Transition de statut : submit (propriétaire), approve|reject (admin).
    action: str | None = Field(default=None, description="submit | approve | reject")


@router.patch("/time-entries/{entry_id}", response_model=TimeEntryOut)
async def update_time_entry(
    entry_id: uuid.UUID,
    payload: UpdateTimeEntry,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> TimeEntryOut:
    """Édite un brouillon (propriétaire) ou fait transiter le statut.

    - `submit` : propriétaire, draft → submitted.
    - `approve`/`reject` : rôle admin, submitted → approved/rejected."""
    entry = await session.get(TimeEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="time_entry_not_found")

    is_owner = entry.consultant_user_id == principal.user_id
    is_admin = "admin:users" in principal.scopes

    # Édition des champs : propriétaire, brouillon uniquement.
    if payload.minutes is not None or payload.billable is not None or payload.activity is not None:
        if not is_owner or entry.status != _OWNER_EDITABLE:
            raise HTTPException(status_code=409, detail="only_owner_can_edit_draft")
        if payload.minutes is not None:
            entry.minutes = payload.minutes
        if payload.billable is not None:
            entry.billable = payload.billable
        if payload.activity is not None:
            entry.activity = payload.activity

    if payload.action == "submit":
        if not is_owner or entry.status != "draft":
            raise HTTPException(status_code=409, detail="cannot_submit")
        entry.status = "submitted"
    elif payload.action in ("approve", "reject"):
        if not is_admin:
            raise HTTPException(status_code=403, detail="admin_required_to_review")
        if entry.status != "submitted":
            raise HTTPException(status_code=409, detail="not_submitted")
        entry.status = "approved" if payload.action == "approve" else "rejected"
    elif payload.action is not None:
        raise HTTPException(status_code=422, detail=f"invalid_action: {payload.action}")

    await session.commit()
    await session.refresh(entry)
    return _to_out(entry)


# ---------------------------------------------------------------------------
# Économie de la mission (agrégat) — réservé admin
# ---------------------------------------------------------------------------
@router.get("/engagements/{mission_id}", summary="Économie d'une mission (honoraires/marge/WIP)")
async def engagement_economics(
    mission_id: uuid.UUID,
    _admin: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    mission = await session.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission_not_found")
    rows = (
        (await session.execute(select(TimeEntry).where(TimeEntry.mission_id == mission_id)))
        .scalars()
        .all()
    )
    entries = [
        {
            "minutes": e.minutes,
            "bill_rate": e.bill_rate,
            "cost_rate": e.cost_rate,
            "billable": e.billable,
            "status": e.status,
        }
        for e in rows
    ]
    econ = compute_engagement_economics(entries)
    return {"mission_id": str(mission_id), "offre": mission.offre, **econ}


# ---------------------------------------------------------------------------
# Taux d'occupation par consultant — réservé admin
# ---------------------------------------------------------------------------
def _business_days(year: int, month: int) -> int:
    """Jours ouvrés (lun–ven) du mois."""
    days = monthrange(year, month)[1]
    return sum(1 for d in range(1, days + 1) if date(year, month, d).weekday() < 5)


class UtilizationRow(BaseModel):
    consultant_user_id: uuid.UUID
    worked_minutes: int
    billable_minutes: int
    available_minutes: int
    occupation_pct: int | None
    activity_pct: int | None


@router.get("/utilization", response_model=list[UtilizationRow], summary="Taux d'occupation")
async def utilization(
    period: str | None = Query(default=None, description="Mois YYYY-MM (défaut : mois courant)"),
    _admin: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[UtilizationRow]:
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
    available = round(_business_days(year, month) * settings.PSA_HOURS_PER_DAY * 60)

    rows = (
        await session.execute(
            select(
                TimeEntry.consultant_user_id,
                func.coalesce(func.sum(TimeEntry.minutes), 0),
                func.coalesce(
                    func.sum(case((TimeEntry.billable.is_(True), TimeEntry.minutes), else_=0)),
                    0,
                ),
            )
            .where(
                TimeEntry.entry_date >= start,
                TimeEntry.entry_date < end,
                TimeEntry.status != "rejected",
            )
            .group_by(TimeEntry.consultant_user_id)
        )
    ).all()

    out: list[UtilizationRow] = []
    for consultant_id, worked, billable in rows:
        u = compute_utilization(
            worked_minutes=int(worked),
            billable_minutes=int(billable),
            available_minutes=available,
        )
        out.append(UtilizationRow(consultant_user_id=consultant_id, **u))
    out.sort(key=lambda r: r.billable_minutes, reverse=True)
    return out


@router.get("/rate-card", summary="Barème d'honoraires par grade")
async def rate_card(
    _admin: Principal = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, dict[str, Any]]:
    return load_rate_card(settings)
