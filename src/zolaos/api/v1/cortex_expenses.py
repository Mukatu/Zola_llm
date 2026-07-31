"""Cockpit cabinet — notes de frais (Zolacortex).

L'autre engagement du consultant sur une mission (avec le temps). Réservé profil
**cortex** : un consultant saisit/soumet SES frais ; l'approbation et la synthèse
sont réservées au rôle admin. Un frais **facturable** approuvé devient un débours
**refacturable** (repris dans la facture d'honoraires) ; approuvé, il est un **coût**.
Même gouvernance que les feuilles de temps (draft → submitted → approved).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.db.models import Expense, Mission
from zolaos.db.session import get_session
from zolaos.psa import EXPENSE_CATEGORIES, summarize_expenses

_log = get_logger("zolaos.api.v1.cortex_expenses")

router = APIRouter(
    prefix="/v1/cortex/expenses",
    tags=["cortex", "expenses"],
    dependencies=[Depends(require_cortex)],
)

_OWNER_EDITABLE = "draft"


class ExpenseOut(BaseModel):
    id: uuid.UUID
    consultant_user_id: uuid.UUID
    mission_id: uuid.UUID
    expense_date: date
    category: str
    amount: int
    billable: bool
    description: str
    status: str
    invoice_id: uuid.UUID | None


def _to_out(e: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=e.id,
        consultant_user_id=e.consultant_user_id,
        mission_id=e.mission_id,
        expense_date=e.expense_date,
        category=e.category,
        amount=e.amount,
        billable=e.billable,
        description=e.description,
        status=e.status,
        invoice_id=e.invoice_id,
    )


class CreateExpense(BaseModel):
    mission_id: uuid.UUID
    expense_date: date
    category: str
    amount: int = Field(gt=0)
    billable: bool = True
    description: str = Field(default="", max_length=1000)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: CreateExpense,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> ExpenseOut:
    """Saisit un frais pour le consultant courant (étape brouillon)."""
    if payload.category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"invalid_category: {payload.category}")
    mission = await session.get(Mission, payload.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission_not_found")

    expense = Expense(
        consultant_user_id=principal.user_id,
        mission_id=payload.mission_id,
        expense_date=payload.expense_date,
        category=payload.category,
        amount=payload.amount,
        billable=payload.billable,
        description=payload.description,
        status="draft",
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    _log.info("psa.expense.created", extra={"expense_id": str(expense.id)})
    return _to_out(expense)


@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    mission_id: uuid.UUID | None = Query(default=None),
    mine: bool = Query(default=True),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> list[ExpenseOut]:
    stmt = select(Expense).order_by(Expense.expense_date.desc()).limit(limit)
    if mine:
        stmt = stmt.where(Expense.consultant_user_id == principal.user_id)
    if mission_id is not None:
        stmt = stmt.where(Expense.mission_id == mission_id)
    if status_filter is not None:
        stmt = stmt.where(Expense.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(e) for e in rows]


class UpdateExpense(BaseModel):
    amount: int | None = Field(default=None, gt=0)
    billable: bool | None = None
    category: str | None = None
    description: str | None = Field(default=None, max_length=1000)
    action: str | None = Field(default=None, description="submit | approve | reject")


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    payload: UpdateExpense,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> ExpenseOut:
    """Édite un brouillon (propriétaire) ou fait transiter le statut (submit /
    approve|reject en admin)."""
    expense = await session.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="expense_not_found")

    is_owner = expense.consultant_user_id == principal.user_id
    is_admin = "admin:users" in principal.scopes

    if (
        payload.amount is not None
        or payload.billable is not None
        or payload.category is not None
        or payload.description is not None
    ):
        if not is_owner or expense.status != _OWNER_EDITABLE:
            raise HTTPException(status_code=409, detail="only_owner_can_edit_draft")
        if payload.category is not None:
            if payload.category not in EXPENSE_CATEGORIES:
                raise HTTPException(status_code=422, detail=f"invalid_category: {payload.category}")
            expense.category = payload.category
        if payload.amount is not None:
            expense.amount = payload.amount
        if payload.billable is not None:
            expense.billable = payload.billable
        if payload.description is not None:
            expense.description = payload.description

    if payload.action == "submit":
        if not is_owner or expense.status != "draft":
            raise HTTPException(status_code=409, detail="cannot_submit")
        expense.status = "submitted"
    elif payload.action in ("approve", "reject"):
        if not is_admin:
            raise HTTPException(status_code=403, detail="admin_required_to_review")
        if expense.status != "submitted":
            raise HTTPException(status_code=409, detail="not_submitted")
        expense.status = "approved" if payload.action == "approve" else "rejected"
    elif payload.action is not None:
        raise HTTPException(status_code=422, detail=f"invalid_action: {payload.action}")

    await session.commit()
    await session.refresh(expense)
    return _to_out(expense)


@router.get("/mission/{mission_id}/summary", summary="Synthèse des frais d'une mission")
async def expenses_summary(
    mission_id: uuid.UUID,
    _admin: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = (
        (await session.execute(select(Expense).where(Expense.mission_id == mission_id)))
        .scalars()
        .all()
    )
    items = [
        {"amount": e.amount, "billable": e.billable, "status": e.status, "category": e.category}
        for e in rows
    ]
    return {"mission_id": str(mission_id), **summarize_expenses(items)}
