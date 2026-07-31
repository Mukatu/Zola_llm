"""Cockpit cabinet — staffing / plan de charge (Zolacortex).

La planification **prospective** des consultants : qui travaille sur quelle mission,
quelle semaine, pour quelle capacité. Agrégées, les affectations donnent le **plan de
charge** (charge allouée vs capacité, sur-affectation, disponibilité) — le pendant
prévisionnel du taux d'occupation (rétrospectif). Acte de gestion → réservé au profil
**cortex** + rôle **admin**. Mutations sous CSRF.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import Assignment, Mission, User
from zolaos.db.session import get_session
from zolaos.staffing import load_row, monday_of, week_capacity_minutes

_log = get_logger("zolaos.api.v1.cortex_staffing")

router = APIRouter(
    prefix="/v1/cortex/staffing",
    tags=["cortex", "staffing"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    consultant_user_id: uuid.UUID
    mission_id: uuid.UUID
    week_start: date
    allocated_minutes: int
    note: str


def _to_out(a: Assignment) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        consultant_user_id=a.consultant_user_id,
        mission_id=a.mission_id,
        week_start=a.week_start,
        allocated_minutes=a.allocated_minutes,
        note=a.note,
    )


# ---------------------------------------------------------------------------
# Affectation (upsert par consultant × mission × semaine)
# ---------------------------------------------------------------------------
class UpsertAssignment(BaseModel):
    consultant_user_id: uuid.UUID
    mission_id: uuid.UUID
    week_start: date  # une date quelconque de la semaine ; normalisée au lundi
    allocated_minutes: int = Field(gt=0, le=7 * 24 * 60)
    note: str = Field(default="", max_length=500)


@router.post("", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def upsert_assignment(
    payload: UpsertAssignment,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> AssignmentOut:
    """Affecte (ou re-planifie) un consultant sur une mission pour une semaine.

    La semaine est **normalisée au lundi** ; ré-affecter le même trio met à jour la
    ligne existante (une affectation par consultant × mission × semaine)."""
    if (await session.get(User, payload.consultant_user_id)) is None:
        raise HTTPException(status_code=404, detail="consultant_not_found")
    if (await session.get(Mission, payload.mission_id)) is None:
        raise HTTPException(status_code=404, detail="mission_not_found")

    monday = monday_of(payload.week_start)
    existing = (
        await session.execute(
            select(Assignment).where(
                Assignment.consultant_user_id == payload.consultant_user_id,
                Assignment.mission_id == payload.mission_id,
                Assignment.week_start == monday,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.allocated_minutes = payload.allocated_minutes
        existing.note = payload.note
        assignment = existing
    else:
        assignment = Assignment(
            consultant_user_id=payload.consultant_user_id,
            mission_id=payload.mission_id,
            week_start=monday,
            allocated_minutes=payload.allocated_minutes,
            note=payload.note,
            created_by_user_id=principal.user_id,
        )
        session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    _log.info("staffing.assignment.upserted", extra={"assignment_id": str(assignment.id)})
    return _to_out(assignment)


@router.get("", response_model=list[AssignmentOut])
async def list_assignments(
    consultant_user_id: uuid.UUID | None = Query(default=None),
    mission_id: uuid.UUID | None = Query(default=None),
    from_week: date | None = Query(default=None, alias="from"),
    to_week: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=500, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentOut]:
    stmt = select(Assignment).order_by(Assignment.week_start).limit(limit)
    if consultant_user_id is not None:
        stmt = stmt.where(Assignment.consultant_user_id == consultant_user_id)
    if mission_id is not None:
        stmt = stmt.where(Assignment.mission_id == mission_id)
    if from_week is not None:
        stmt = stmt.where(Assignment.week_start >= monday_of(from_week))
    if to_week is not None:
        stmt = stmt.where(Assignment.week_start <= monday_of(to_week))
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(a) for a in rows]


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> Response:
    a = await session.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment_not_found")
    await session.delete(a)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Plan de charge (grille consultant × semaine)
# ---------------------------------------------------------------------------
class WeekLoad(BaseModel):
    week_start: date
    allocated_minutes: int
    capacity_minutes: int
    available_minutes: int
    load_pct: int | None
    over_allocated: bool


class ConsultantLoad(BaseModel):
    consultant_user_id: uuid.UUID
    total_allocated_minutes: int
    avg_load_pct: int | None
    over_weeks: int  # nb de semaines en sur-affectation
    weeks: list[WeekLoad]


class LoadResponse(BaseModel):
    from_week: date
    weeks: int
    capacity_minutes: int  # capacité hebdomadaire d'un consultant
    consultants: list[ConsultantLoad]


@router.get("/load", response_model=LoadResponse, summary="Plan de charge (capacité vs alloué)")
async def load_plan(
    from_week: date | None = Query(
        default=None, alias="from", description="Début (défaut : cette semaine)"
    ),
    weeks: int = Query(default=6, ge=1, le=52),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LoadResponse:
    from_monday = monday_of(from_week) if from_week is not None else monday_of(date.today())
    horizon = [from_monday + timedelta(days=7 * i) for i in range(weeks)]
    end = from_monday + timedelta(days=7 * weeks)
    capacity = week_capacity_minutes(settings.PSA_HOURS_PER_DAY)

    rows = (
        (
            await session.execute(
                select(Assignment).where(
                    Assignment.week_start >= from_monday, Assignment.week_start < end
                )
            )
        )
        .scalars()
        .all()
    )
    # allocated[(consultant, week)] = somme (un consultant peut cumuler plusieurs missions).
    allocated: dict[tuple[Any, date], int] = {}
    consultants: list[Any] = []
    for a in rows:
        key = (a.consultant_user_id, a.week_start)
        allocated[key] = allocated.get(key, 0) + a.allocated_minutes
        if a.consultant_user_id not in consultants:
            consultants.append(a.consultant_user_id)

    out: list[ConsultantLoad] = []
    for cid in consultants:
        week_rows: list[WeekLoad] = []
        total = over = 0
        for w in horizon:
            r = load_row(allocated.get((cid, w), 0), capacity)
            week_rows.append(WeekLoad(week_start=w, **r))
            total += r["allocated_minutes"]
            over += 1 if r["over_allocated"] else 0
        total_capacity = capacity * weeks
        avg = round(total / total_capacity * 100) if total_capacity else None
        out.append(
            ConsultantLoad(
                consultant_user_id=cid,
                total_allocated_minutes=total,
                avg_load_pct=avg,
                over_weeks=over,
                weeks=week_rows,
            )
        )
    out.sort(key=lambda c: c.total_allocated_minutes, reverse=True)
    return LoadResponse(
        from_week=from_monday, weeks=weeks, capacity_minutes=capacity, consultants=out
    )
