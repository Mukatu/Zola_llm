"""Repository CRUD du système de référence léger (Factures).

Pattern repository sur AsyncSession : isole l'accès aux données. Multi-tenant
(filtrage par `tenant_id`). Réutilisable pour les autres entités (P2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.store_models import (
    AbsenceRecord,
    ApplicationRecord,
    CandidateRecord,
    ContractRecord,
    EmployeeRecord,
    EmployeeSkillRecord,
    InterviewRecord,
    InvoiceRecord,
    JobRoleRecord,
    JournalEntryRecord,
    RoleSkillRecord,
    SkillRecord,
    StockItemRecord,
    VacancyRecord,
)


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


class JournalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> JournalEntryRecord:
        rec = JournalEntryRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def list(self, *, tenant_id: str) -> list[JournalEntryRecord]:
        stmt = (
            select(JournalEntryRecord)
            .where(JournalEntryRecord.tenant_id == tenant_id)
            .order_by(JournalEntryRecord.date_ecriture.desc())
        )
        return list(await self._s.scalars(stmt))

    async def delete(self, entry_id: str, *, tenant_id: str) -> bool:
        rec = await self._s.get(JournalEntryRecord, entry_id)
        if rec is None or rec.tenant_id != tenant_id:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class StockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> StockItemRecord:
        rec = StockItemRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def get(self, item_id: str, *, tenant_id: str) -> StockItemRecord | None:
        rec = await self._s.get(StockItemRecord, item_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def list(self, *, tenant_id: str) -> list[StockItemRecord]:
        stmt = (
            select(StockItemRecord)
            .where(StockItemRecord.tenant_id == tenant_id)
            .order_by(StockItemRecord.sku)
        )
        return list(await self._s.scalars(stmt))

    async def update(
        self, item_id: str, *, tenant_id: str, fields: dict[str, Any]
    ) -> StockItemRecord | None:
        rec = await self.get(item_id, tenant_id=tenant_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec

    async def delete(self, item_id: str, *, tenant_id: str) -> bool:
        rec = await self.get(item_id, tenant_id=tenant_id)
        if rec is None:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> EmployeeRecord:
        rec = EmployeeRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def get(self, emp_id: str, *, tenant_id: str) -> EmployeeRecord | None:
        rec = await self._s.get(EmployeeRecord, emp_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def list(self, *, tenant_id: str) -> list[EmployeeRecord]:
        stmt = (
            select(EmployeeRecord)
            .where(EmployeeRecord.tenant_id == tenant_id)
            .order_by(EmployeeRecord.matricule)
        )
        return list(await self._s.scalars(stmt))

    async def update(
        self, emp_id: str, *, tenant_id: str, fields: dict[str, Any]
    ) -> EmployeeRecord | None:
        rec = await self.get(emp_id, tenant_id=tenant_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec

    async def delete(self, emp_id: str, *, tenant_id: str) -> bool:
        rec = await self.get(emp_id, tenant_id=tenant_id)
        if rec is None:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class ContractRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> ContractRecord:
        rec = ContractRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def list(self, *, tenant_id: str) -> list[ContractRecord]:
        stmt = select(ContractRecord).where(ContractRecord.tenant_id == tenant_id)
        return list(await self._s.scalars(stmt))

    async def delete(self, contract_id: str, *, tenant_id: str) -> bool:
        rec = await self._s.get(ContractRecord, contract_id)
        if rec is None or rec.tenant_id != tenant_id:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class AbsenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> AbsenceRecord:
        rec = AbsenceRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def list(self, *, tenant_id: str) -> list[AbsenceRecord]:
        stmt = select(AbsenceRecord).where(AbsenceRecord.tenant_id == tenant_id)
        return list(await self._s.scalars(stmt))

    async def delete(self, absence_id: str, *, tenant_id: str) -> bool:
        rec = await self._s.get(AbsenceRecord, absence_id)
        if rec is None or rec.tenant_id != tenant_id:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class _SimpleRepo:
    """CRUD minimal (create/list/delete) pour les référentiels."""

    model: type[Any]

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> Any:
        rec = self.model(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def list(self, *, tenant_id: str) -> list[Any]:
        stmt = select(self.model).where(self.model.tenant_id == tenant_id)
        return list(await self._s.scalars(stmt))

    async def delete(self, rec_id: str, *, tenant_id: str) -> bool:
        rec = await self._s.get(self.model, rec_id)
        if rec is None or rec.tenant_id != tenant_id:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class JobRoleRepository(_SimpleRepo):
    model = JobRoleRecord


class SkillRepository(_SimpleRepo):
    model = SkillRecord


class RoleSkillRepository(_SimpleRepo):
    model = RoleSkillRecord


class VacancyRepository(_SimpleRepo):
    model = VacancyRecord


class CandidateRepository(_SimpleRepo):
    model = CandidateRecord


class InterviewRepository(_SimpleRepo):
    model = InterviewRecord


class ApplicationRepository(_SimpleRepo):
    model = ApplicationRecord

    async def get(self, app_id: str, *, tenant_id: str) -> ApplicationRecord | None:
        rec = await self._s.get(ApplicationRecord, app_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def update(
        self, app_id: str, *, tenant_id: str, fields: dict[str, Any]
    ) -> ApplicationRecord | None:
        rec = await self.get(app_id, tenant_id=tenant_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec


class EmployeeSkillRepository(_SimpleRepo):
    model = EmployeeSkillRecord

    async def set_note(
        self, *, tenant_id: str, matricule: str, code_competence: str, note: int
    ) -> EmployeeSkillRecord:
        """Upsert : une seule note par (collaborateur, compétence)."""
        stmt = select(EmployeeSkillRecord).where(
            EmployeeSkillRecord.tenant_id == tenant_id,
            EmployeeSkillRecord.employee_matricule == matricule,
            EmployeeSkillRecord.code_competence == code_competence,
        )
        existing = (await self._s.scalars(stmt)).first()
        if existing is not None:
            existing.note = note
            await self._s.flush()
            return existing
        rec = EmployeeSkillRecord(
            tenant_id=tenant_id,
            employee_matricule=matricule,
            code_competence=code_competence,
            note=note,
        )
        self._s.add(rec)
        await self._s.flush()
        return rec
