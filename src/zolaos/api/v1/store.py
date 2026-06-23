"""Système de référence léger — Factures (CRUD) + clôture continue.

Profil box. Persistance des factures (`store_invoices`) + endpoint de
**réconciliation temps réel** : à chaque lot de mouvements, on relettre le
registre stocké (clôture continue). Multi-tenant via `tenant_id` (défaut local).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.erp.reconciliation import reconcilier
from zolaos.connectors.models import BankTransaction, Invoice
from zolaos.db.session import get_session
from zolaos.db.store_repo import InvoiceRepository

router = APIRouter(prefix="/v1/erp", tags=["store"])


# ---------------------------------------------------------------- schémas


class InvoiceIn(BaseModel):
    numero: str
    sens: str = "vente"
    tiers: str
    date_emission: date
    date_echeance: date | None = None
    montant_ht_xaf: Decimal = Decimal("0")
    montant_tva_xaf: Decimal | None = None
    montant_ttc_xaf: Decimal = Decimal("0")
    devise: str = "XAF"
    payee: bool = False
    country: str = "cg"


class InvoicePatch(BaseModel):
    tiers: str | None = None
    date_echeance: date | None = None
    montant_ttc_xaf: Decimal | None = None
    payee: bool | None = None


class ReconcileIn(BaseModel):
    transactions: list[BankTransaction] = Field(default_factory=list)
    fenetre_jours: int = Field(default=5, ge=0, le=60)


# ---------------------------------------------------------------- CRUD factures


@router.post("/invoices", status_code=status.HTTP_201_CREATED, summary="Créer une facture")
async def create_invoice(
    body: InvoiceIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/invoices", summary="Lister les factures")
async def list_invoices(
    tenant_id: str = "local",
    sens: str | None = None,
    payee: bool | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rows = await InvoiceRepository(session).list(tenant_id=tenant_id, sens=sens, payee=payee)
    return {"invoices": [r.to_dict() for r in rows]}


@router.get("/invoices/{invoice_id}", summary="Lire une facture")
async def get_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).get(invoice_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    return rec.to_dict()


@router.patch("/invoices/{invoice_id}", summary="Mettre à jour une facture")
async def patch_invoice(
    invoice_id: str,
    body: InvoicePatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).update(
        invoice_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return rec.to_dict()


@router.post("/invoices/{invoice_id}/pay", summary="Marquer payée")
async def pay_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rec = await InvoiceRepository(session).mark_paid(invoice_id, tenant_id=tenant_id)
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/invoices/{invoice_id}", summary="Supprimer une facture")
async def delete_invoice(
    invoice_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    ok = await InvoiceRepository(session).delete(invoice_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invoice_not_found")
    await session.commit()
    return {"deleted": invoice_id}


# ---------------------------------------------------------------- clôture continue


@router.post("/reconcile", summary="Réconciliation temps réel (clôture continue)")
async def reconcile(
    body: ReconcileIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, Any]:
    rows = await InvoiceRepository(session).list(tenant_id=tenant_id, sens="vente", payee=False)
    invoices = [
        Invoice(
            id_externe=r.id,
            numero=r.numero,
            sens="vente",
            tiers=r.tiers,
            date_emission=r.date_emission,
            montant_ht_xaf=r.montant_ht_xaf,
            montant_ttc_xaf=r.montant_ttc_xaf,
            payee=r.payee,
            country=r.country,
        )
        for r in rows
    ]
    report = reconcilier(invoices, body.transactions, fenetre_jours=body.fenetre_jours)
    return {
        "rapprochements": [asdict(x) for x in report.rapprochements],
        "factures_en_attente": [asdict(x) for x in report.factures_en_attente],
        "mouvements_non_rapproches": report.mouvements_non_rapproches,
        "cloture": asdict(report.cloture) if report.cloture else None,
    }
