"""Cockpit cabinet — facturation d'honoraires (Zolacortex).

Aval du PSA : le cabinet facture son client à partir des feuilles de temps
**facturables approuvées** d'une mission. Réservé profil **cortex** + rôle **admin**
(acte financier). Une facture regroupe les saisies non encore facturées, fige le
total, puis suit son cycle draft → issued → paid (ou cancelled = libère les saisies).
`GET …/aging` donne l'échéancier (base des relances). Émission/encaissement/annulation
sont **audités** (`audit.log`).

À distinguer de la facturation d'**usage** plateforme (`api/v1/cortex_billing.py`,
éditeur → client) : ici c'est **cabinet → son client**, en honoraires.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.audit import record_audit
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.db.models import Invoice, Mission, TimeEntry
from zolaos.db.session import get_session
from zolaos.psa import entry_amounts
from zolaos.psa.invoicing import aging_bucket, next_invoice_number

_log = get_logger("zolaos.api.v1.cortex_invoices")

router = APIRouter(
    prefix="/v1/cortex/invoices",
    tags=["cortex", "invoices"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)


class InvoiceOut(BaseModel):
    id: uuid.UUID
    number: str
    mission_id: uuid.UUID
    client_tenant_id: uuid.UUID
    status: str
    amount: int
    currency: str
    issued_date: date | None
    due_date: date | None
    paid_date: date | None
    notes: str
    created_at: datetime


def _to_out(inv: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=inv.id,
        number=inv.number,
        mission_id=inv.mission_id,
        client_tenant_id=inv.client_tenant_id,
        status=inv.status,
        amount=inv.amount,
        currency=inv.currency,
        issued_date=inv.issued_date,
        due_date=inv.due_date,
        paid_date=inv.paid_date,
        notes=inv.notes,
        created_at=inv.created_at,
    )


async def _get_or_404(session: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    inv = await session.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    return inv


# ---------------------------------------------------------------------------
# Création : regroupe les temps facturables approuvés d'une mission
# ---------------------------------------------------------------------------
class CreateInvoice(BaseModel):
    mission_id: uuid.UUID
    notes: str = Field(default="", max_length=1000)


@router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: CreateInvoice,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> InvoiceOut:
    """Crée une facture **brouillon** à partir des feuilles de temps facturables
    approuvées, non encore facturées, de la mission. 409 s'il n'y a rien à facturer."""
    mission = await session.get(Mission, payload.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission_not_found")

    entries = (
        (
            await session.execute(
                select(TimeEntry).where(
                    TimeEntry.mission_id == payload.mission_id,
                    TimeEntry.status == "approved",
                    TimeEntry.billable.is_(True),
                    TimeEntry.invoice_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="nothing_to_invoice")

    amount = sum(
        entry_amounts(
            minutes=e.minutes, bill_rate=e.bill_rate, cost_rate=e.cost_rate, billable=True
        )["honoraires"]
        for e in entries
    )

    year = datetime.now(UTC).year
    count = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.number.like(f"FACT-{year:04d}-%"))
        )
    ).scalar_one()
    number = next_invoice_number(year, int(count))

    invoice = Invoice(
        mission_id=payload.mission_id,
        client_tenant_id=mission.client_tenant_id,
        number=number,
        status="draft",
        amount=int(amount),
        currency="XAF",
        notes=payload.notes,
        created_by_user_id=principal.user_id,
    )
    session.add(invoice)
    await session.flush()
    for e in entries:
        e.invoice_id = invoice.id
    await session.commit()
    await session.refresh(invoice)
    _log.info(
        "invoice.created",
        extra={"invoice_id": str(invoice.id), "number": number, "entries": len(entries)},
    )
    return _to_out(invoice)


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------
@router.get("", response_model=list[InvoiceOut])
async def list_invoices(
    client_tenant_id: uuid.UUID | None = Query(default=None),
    mission_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[InvoiceOut]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    if client_tenant_id is not None:
        stmt = stmt.where(Invoice.client_tenant_id == client_tenant_id)
    if mission_id is not None:
        stmt = stmt.where(Invoice.mission_id == mission_id)
    if status_filter is not None:
        stmt = stmt.where(Invoice.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(i) for i in rows]


# ---------------------------------------------------------------------------
# Échéancier / aging (base des relances) — AVANT /{invoice_id}
# ---------------------------------------------------------------------------
class AgingLine(BaseModel):
    id: uuid.UUID
    number: str
    client_tenant_id: uuid.UUID
    amount: int
    due_date: date | None
    days_overdue: int
    bucket: str


class AgingResponse(BaseModel):
    currency: str
    total_outstanding: int
    buckets: dict[str, int]  # tranche → montant en cours
    invoices: list[AgingLine]


@router.get("/aging", response_model=AgingResponse, summary="Échéancier des créances (relances)")
async def aging(
    session: AsyncSession = Depends(get_session),
) -> AgingResponse:
    """Créances **émises non payées**, ventilées par ancienneté (base des relances)."""
    today = datetime.now(UTC).date()
    rows = (
        (await session.execute(select(Invoice).where(Invoice.status == "issued"))).scalars().all()
    )
    buckets: dict[str, int] = {}
    lines: list[AgingLine] = []
    total = 0
    currency = "XAF"
    for inv in rows:
        currency = inv.currency
        days_overdue = (today - inv.due_date).days if inv.due_date is not None else 0
        bucket = aging_bucket(days_overdue)
        buckets[bucket] = buckets.get(bucket, 0) + inv.amount
        total += inv.amount
        lines.append(
            AgingLine(
                id=inv.id,
                number=inv.number,
                client_tenant_id=inv.client_tenant_id,
                amount=inv.amount,
                due_date=inv.due_date,
                days_overdue=days_overdue,
                bucket=bucket,
            )
        )
    lines.sort(key=lambda x: x.days_overdue, reverse=True)
    return AgingResponse(
        currency=currency, total_outstanding=total, buckets=buckets, invoices=lines
    )


# ---------------------------------------------------------------------------
# Détail (avec les saisies rattachées)
# ---------------------------------------------------------------------------
class EntryBrief(BaseModel):
    id: uuid.UUID
    consultant_user_id: uuid.UUID
    entry_date: date
    minutes: int
    activity: str
    honoraires: int


class InvoiceDetail(InvoiceOut):
    entries: list[EntryBrief]


@router.get("/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> InvoiceDetail:
    inv = await _get_or_404(session, invoice_id)
    rows = (
        (await session.execute(select(TimeEntry).where(TimeEntry.invoice_id == invoice_id)))
        .scalars()
        .all()
    )
    entries = [
        EntryBrief(
            id=e.id,
            consultant_user_id=e.consultant_user_id,
            entry_date=e.entry_date,
            minutes=e.minutes,
            activity=e.activity,
            honoraires=entry_amounts(
                minutes=e.minutes, bill_rate=e.bill_rate, cost_rate=e.cost_rate, billable=e.billable
            )["honoraires"],
        )
        for e in rows
    ]
    return InvoiceDetail(**_to_out(inv).model_dump(), entries=entries)


# ---------------------------------------------------------------------------
# Cycle de vie (audité)
# ---------------------------------------------------------------------------
class IssueInvoice(BaseModel):
    due_days: int = Field(default=30, ge=0, le=365)


@router.post("/{invoice_id}/issue", response_model=InvoiceOut)
async def issue_invoice(
    invoice_id: uuid.UUID,
    payload: IssueInvoice,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> InvoiceOut:
    """Émet la facture (draft → issued) : fixe la date d'émission et l'échéance."""
    inv = await _get_or_404(session, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"not_draft (status={inv.status})")
    today = datetime.now(UTC).date()
    inv.status = "issued"
    inv.issued_date = today
    inv.due_date = today + timedelta(days=payload.due_days)
    await record_audit(
        session,
        actor=principal,
        action="invoice.issued",
        summary=f"Facture {inv.number} émise ({inv.amount} {inv.currency})",
        target_type="tenant",
        target_id=inv.client_tenant_id,
        extra={"number": inv.number, "amount": inv.amount, "due_date": inv.due_date.isoformat()},
        request=request,
    )
    await session.commit()
    await session.refresh(inv)
    return _to_out(inv)


@router.post("/{invoice_id}/pay", response_model=InvoiceOut)
async def pay_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> InvoiceOut:
    """Enregistre l'encaissement (issued → paid)."""
    inv = await _get_or_404(session, invoice_id)
    if inv.status != "issued":
        raise HTTPException(status_code=409, detail=f"not_issued (status={inv.status})")
    inv.status = "paid"
    inv.paid_date = datetime.now(UTC).date()
    await record_audit(
        session,
        actor=principal,
        action="invoice.paid",
        summary=f"Facture {inv.number} encaissée ({inv.amount} {inv.currency})",
        target_type="tenant",
        target_id=inv.client_tenant_id,
        extra={"number": inv.number, "amount": inv.amount},
        request=request,
    )
    await session.commit()
    await session.refresh(inv)
    return _to_out(inv)


@router.post("/{invoice_id}/cancel", response_model=InvoiceOut)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> InvoiceOut:
    """Annule une facture (draft|issued → cancelled) et **libère** les saisies
    rattachées (elles redeviennent facturables)."""
    inv = await _get_or_404(session, invoice_id)
    if inv.status not in ("draft", "issued"):
        raise HTTPException(status_code=409, detail=f"cannot_cancel (status={inv.status})")
    # Libère les feuilles de temps rattachées.
    rows = (
        (await session.execute(select(TimeEntry).where(TimeEntry.invoice_id == invoice_id)))
        .scalars()
        .all()
    )
    for e in rows:
        e.invoice_id = None
    inv.status = "cancelled"
    await record_audit(
        session,
        actor=principal,
        action="invoice.cancelled",
        summary=f"Facture {inv.number} annulée",
        target_type="tenant",
        target_id=inv.client_tenant_id,
        extra={"number": inv.number, "released_entries": len(rows)},
        request=request,
    )
    await session.commit()
    await session.refresh(inv)
    return _to_out(inv)
