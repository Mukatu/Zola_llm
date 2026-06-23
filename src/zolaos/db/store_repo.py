"""Repository CRUD du système de référence léger (Factures).

Pattern repository sur AsyncSession : isole l'accès aux données. Multi-tenant
(filtrage par `tenant_id`). Réutilisable pour les autres entités (P2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.store_models import InvoiceRecord


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> InvoiceRecord:
        rec = InvoiceRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def get(self, invoice_id: str, *, tenant_id: str) -> InvoiceRecord | None:
        rec = await self._s.get(InvoiceRecord, invoice_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def list(
        self, *, tenant_id: str, sens: str | None = None, payee: bool | None = None
    ) -> list[InvoiceRecord]:
        stmt = select(InvoiceRecord).where(InvoiceRecord.tenant_id == tenant_id)
        if sens is not None:
            stmt = stmt.where(InvoiceRecord.sens == sens)
        if payee is not None:
            stmt = stmt.where(InvoiceRecord.payee == payee)
        stmt = stmt.order_by(InvoiceRecord.date_emission.desc())
        return list(await self._s.scalars(stmt))

    async def update(
        self, invoice_id: str, *, tenant_id: str, fields: dict[str, Any]
    ) -> InvoiceRecord | None:
        rec = await self.get(invoice_id, tenant_id=tenant_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec

    async def mark_paid(
        self, invoice_id: str, *, tenant_id: str, payee: bool = True
    ) -> InvoiceRecord | None:
        return await self.update(invoice_id, tenant_id=tenant_id, fields={"payee": payee})

    async def delete(self, invoice_id: str, *, tenant_id: str) -> bool:
        rec = await self.get(invoice_id, tenant_id=tenant_id)
        if rec is None:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True
