"""Repository CRUD du système de référence léger (Factures).

Pattern repository sur AsyncSession : isole l'accès aux données. Multi-tenant
(filtrage par `tenant_id`). Réutilisable pour les autres entités (P2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.store_models import (
    AbsenceRecord,
    AgentFeedbackRecord,
    AmlCaseRecord,
    ApplicationRecord,
    AssetRecord,
    BankAccountRecord,
    BudgetLineRecord,
    CampaignRecord,
    CandidateRecord,
    CashFlowRecord,
    ContractRecord,
    CreditApplicationRecord,
    CustomerRecord,
    DocumentRecord,
    EcheanceRecord,
    EmployeeRecord,
    EmployeeRubriqueRecord,
    EmployeeSkillRecord,
    EngagementRecord,
    EvaluationRecord,
    FxRateRecord,
    IncidentRecord,
    InteractionRecord,
    InterviewRecord,
    InvoiceRecord,
    JobRoleRecord,
    JournalEntryRecord,
    KycRecordRecord,
    LoanInstallmentRecord,
    MandateRecord,
    MarketingContactRecord,
    OpportunityRecord,
    PayrollScaleRecord,
    PayrollScaleValidationRecord,
    PayrollVariableRecord,
    PayslipArchiveRecord,
    PayslipRecord,
    PayslipTemplateRecord,
    ProjectRecord,
    PurchaseBudgetRecord,
    PurchaseOrderRecord,
    QuoteRecord,
    ResolutionRecord,
    RisqueRecord,
    RoleSkillRecord,
    SkillRecord,
    StockItemRecord,
    StockMoveRecord,
    SupplierRecord,
    TrainingEnrollmentRecord,
    TrainingEvaluationRecord,
    TrainingRecord,
    TrainingSessionRecord,
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

    async def get_by_sku(self, sku: str, *, tenant_id: str) -> StockItemRecord | None:
        stmt = select(StockItemRecord).where(
            StockItemRecord.tenant_id == tenant_id, StockItemRecord.sku == sku
        )
        return (await self._s.scalars(stmt)).first()

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

    async def get_by_matricule(self, matricule: str, *, tenant_id: str) -> EmployeeRecord | None:
        stmt = select(EmployeeRecord).where(
            EmployeeRecord.tenant_id == tenant_id,
            EmployeeRecord.matricule == matricule,
        )
        return (await self._s.scalars(stmt)).first()

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


class DocumentRepository(_SimpleRepo):
    model = DocumentRecord


class EvaluationRepository(_SimpleRepo):
    model = EvaluationRecord


class TrainingRepository(_SimpleRepo):
    model = TrainingRecord


class TrainingSessionRepository(_SimpleRepo):
    model = TrainingSessionRecord


class TrainingEnrollmentRepository(_SimpleRepo):
    model = TrainingEnrollmentRecord

    async def update(
        self, rec_id: str, *, tenant_id: str, fields: dict[str, Any]
    ) -> TrainingEnrollmentRecord | None:
        rec = await self._s.get(TrainingEnrollmentRecord, rec_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec


class TrainingEvaluationRepository(_SimpleRepo):
    model = TrainingEvaluationRecord


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


class _CrudRepo(_SimpleRepo):
    """CRUD complet (create/get/list/update/delete), filtré tenant."""

    async def get(self, rec_id: str, *, tenant_id: str) -> Any:
        rec = await self._s.get(self.model, rec_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def update(self, rec_id: str, *, tenant_id: str, fields: dict[str, Any]) -> Any:
        rec = await self.get(rec_id, tenant_id=tenant_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k) and k not in {"id", "tenant_id", "created_at"}:
                setattr(rec, k, v)
        await self._s.flush()
        return rec


class CustomerRepository(_CrudRepo):
    model = CustomerRecord


class OpportunityRepository(_CrudRepo):
    model = OpportunityRecord


class QuoteRepository(_CrudRepo):
    model = QuoteRecord


class SupplierRepository(_CrudRepo):
    model = SupplierRecord


class CreditApplicationRepository(_CrudRepo):
    model = CreditApplicationRecord


class AmlCaseRepository(_CrudRepo):
    model = AmlCaseRecord


class KycRecordRepository(_CrudRepo):
    model = KycRecordRecord


class LoanInstallmentRepository(_CrudRepo):
    model = LoanInstallmentRecord

    async def list_for_application(
        self, application_id: str, *, tenant_id: str
    ) -> list[LoanInstallmentRecord]:
        stmt = (
            select(LoanInstallmentRecord)
            .where(
                LoanInstallmentRecord.tenant_id == tenant_id,
                LoanInstallmentRecord.application_id == application_id,
            )
            .order_by(LoanInstallmentRecord.numero)
        )
        return list(await self._s.scalars(stmt))


class PurchaseOrderRepository(_CrudRepo):
    model = PurchaseOrderRecord


class StockMoveRepository(_CrudRepo):
    model = StockMoveRecord

    async def list(  # type: ignore[override]
        self, *, tenant_id: str, sku: str | None = None
    ) -> list[StockMoveRecord]:
        stmt = select(StockMoveRecord).where(StockMoveRecord.tenant_id == tenant_id)
        if sku is not None:
            stmt = stmt.where(StockMoveRecord.sku == sku)
        stmt = stmt.order_by(StockMoveRecord.date_mouvement.desc())
        return list(await self._s.scalars(stmt))


class PayslipRepository(_CrudRepo):
    model = PayslipRecord

    async def list(  # type: ignore[override]
        self,
        *,
        tenant_id: str,
        periode: str | None = None,
        employee_matricule: str | None = None,
    ) -> list[PayslipRecord]:
        stmt = select(PayslipRecord).where(PayslipRecord.tenant_id == tenant_id)
        if periode is not None:
            stmt = stmt.where(PayslipRecord.periode == periode)
        if employee_matricule is not None:
            stmt = stmt.where(PayslipRecord.employee_matricule == employee_matricule)
        return list(await self._s.scalars(stmt))

    async def upsert(self, data: dict[str, Any]) -> PayslipRecord:
        """Un seul bulletin par (matricule, période)."""
        stmt = select(PayslipRecord).where(
            PayslipRecord.tenant_id == data["tenant_id"],
            PayslipRecord.employee_matricule == data["employee_matricule"],
            PayslipRecord.periode == data["periode"],
        )
        existing = (await self._s.scalars(stmt)).first()
        if existing is not None:
            for k, v in data.items():
                if k not in {"id", "tenant_id", "created_at"}:
                    setattr(existing, k, v)
            await self._s.flush()
            return existing
        rec = PayslipRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec


class EmployeeRubriqueRepository:
    """Affectations de rubriques de paie par salarié — PAIE-6c."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list(
        self, *, tenant_id: str, employee_matricule: str
    ) -> list[EmployeeRubriqueRecord]:
        stmt = select(EmployeeRubriqueRecord).where(
            EmployeeRubriqueRecord.tenant_id == tenant_id,
            EmployeeRubriqueRecord.employee_matricule == employee_matricule,
        )
        return list(await self._s.scalars(stmt))

    async def upsert(
        self, *, tenant_id: str, employee_matricule: str, code: str, valeur: Decimal | None
    ) -> EmployeeRubriqueRecord:
        stmt = select(EmployeeRubriqueRecord).where(
            EmployeeRubriqueRecord.tenant_id == tenant_id,
            EmployeeRubriqueRecord.employee_matricule == employee_matricule,
            EmployeeRubriqueRecord.code == code,
        )
        rec = (await self._s.scalars(stmt)).first()
        if rec is None:
            rec = EmployeeRubriqueRecord(
                tenant_id=tenant_id, employee_matricule=employee_matricule, code=code
            )
            self._s.add(rec)
        rec.valeur = valeur
        await self._s.flush()
        return rec

    async def delete(self, *, tenant_id: str, employee_matricule: str, code: str) -> bool:
        stmt = select(EmployeeRubriqueRecord).where(
            EmployeeRubriqueRecord.tenant_id == tenant_id,
            EmployeeRubriqueRecord.employee_matricule == employee_matricule,
            EmployeeRubriqueRecord.code == code,
        )
        rec = (await self._s.scalars(stmt)).first()
        if rec is None:
            return False
        await self._s.delete(rec)
        await self._s.flush()
        return True


class PayrollVariableRepository:
    """Variables de paie mensuelles par (tenant, matricule, période) — PAIE-8."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self, *, tenant_id: str, employee_matricule: str, periode: str
    ) -> PayrollVariableRecord | None:
        stmt = select(PayrollVariableRecord).where(
            PayrollVariableRecord.tenant_id == tenant_id,
            PayrollVariableRecord.employee_matricule == employee_matricule,
            PayrollVariableRecord.periode == periode,
        )
        return (await self._s.scalars(stmt)).first()

    async def upsert(
        self, *, tenant_id: str, employee_matricule: str, periode: str, payload: dict[str, Any]
    ) -> PayrollVariableRecord:
        rec = await self.get(
            tenant_id=tenant_id, employee_matricule=employee_matricule, periode=periode
        )
        if rec is None:
            rec = PayrollVariableRecord(
                tenant_id=tenant_id, employee_matricule=employee_matricule, periode=periode
            )
            self._s.add(rec)
        rec.payload = payload
        await self._s.flush()
        return rec


class PayslipArchiveRepository:
    """Coffre-fort des bulletins archivés — PAIE-10."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> PayslipArchiveRecord:
        rec = PayslipArchiveRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def get(self, archive_id: str, *, tenant_id: str) -> PayslipArchiveRecord | None:
        rec = await self._s.get(PayslipArchiveRecord, archive_id)
        if rec is None or rec.tenant_id != tenant_id:
            return None
        return rec

    async def list(
        self,
        *,
        tenant_id: str,
        periode: str | None = None,
        employee_matricule: str | None = None,
    ) -> list[PayslipArchiveRecord]:
        stmt = select(PayslipArchiveRecord).where(PayslipArchiveRecord.tenant_id == tenant_id)
        if periode is not None:
            stmt = stmt.where(PayslipArchiveRecord.periode == periode)
        if employee_matricule is not None:
            stmt = stmt.where(PayslipArchiveRecord.employee_matricule == employee_matricule)
        stmt = stmt.order_by(PayslipArchiveRecord.archived_at.desc())
        return list(await self._s.scalars(stmt))


class PayslipTemplateRepository:
    """Modèle de bulletin de paie par tenant — PAIE-7a."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, *, tenant_id: str) -> PayslipTemplateRecord | None:
        stmt = select(PayslipTemplateRecord).where(PayslipTemplateRecord.tenant_id == tenant_id)
        return (await self._s.scalars(stmt)).first()

    async def upsert(self, *, tenant_id: str, payload: dict[str, Any]) -> PayslipTemplateRecord:
        rec = await self.get(tenant_id=tenant_id)
        if rec is None:
            rec = PayslipTemplateRecord(tenant_id=tenant_id)
            self._s.add(rec)
        rec.payload = payload
        await self._s.flush()
        return rec


class PayrollScaleRepository:
    """Barème de paie persisté (override) par (tenant, pays) — PAIE-6a."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, *, tenant_id: str, country: str) -> PayrollScaleRecord | None:
        stmt = select(PayrollScaleRecord).where(
            PayrollScaleRecord.tenant_id == tenant_id,
            PayrollScaleRecord.country == country,
        )
        return (await self._s.scalars(stmt)).first()

    async def upsert(
        self, *, tenant_id: str, country: str, version: str, payload: dict[str, Any]
    ) -> PayrollScaleRecord:
        rec = await self.get(tenant_id=tenant_id, country=country)
        if rec is None:
            rec = PayrollScaleRecord(tenant_id=tenant_id, country=country)
            self._s.add(rec)
        rec.version = version
        rec.payload = payload
        await self._s.flush()
        return rec


class PayrollValidationRepository:
    """Validation experte d'un barème par (tenant, pays, version) — PAIE-5."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self, *, tenant_id: str, country: str, version: str
    ) -> PayrollScaleValidationRecord | None:
        stmt = select(PayrollScaleValidationRecord).where(
            PayrollScaleValidationRecord.tenant_id == tenant_id,
            PayrollScaleValidationRecord.country == country,
            PayrollScaleValidationRecord.version == version,
        )
        return (await self._s.scalars(stmt)).first()

    async def set_validation(
        self,
        *,
        tenant_id: str,
        country: str,
        version: str,
        validated: bool,
        validated_by: str,
        note: str,
    ) -> PayrollScaleValidationRecord:
        rec = await self.get(tenant_id=tenant_id, country=country, version=version)
        now = datetime.now(UTC) if validated else None
        if rec is None:
            rec = PayrollScaleValidationRecord(
                tenant_id=tenant_id, country=country, version=version
            )
            self._s.add(rec)
        rec.validated = validated
        rec.validated_by = validated_by
        rec.note = note
        rec.validated_at = now
        await self._s.flush()
        return rec


class FxRateRepository:
    """Taux de change gouvernés (override tenant) par (tenant, pays) — MULTIDEV-1."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list(self, *, tenant_id: str, country: str) -> list[FxRateRecord]:
        stmt = select(FxRateRecord).where(
            FxRateRecord.tenant_id == tenant_id, FxRateRecord.country == country
        )
        return list((await self._s.scalars(stmt)).all())

    async def get(
        self, *, tenant_id: str, country: str, devise: str
    ) -> FxRateRecord | None:
        stmt = select(FxRateRecord).where(
            FxRateRecord.tenant_id == tenant_id,
            FxRateRecord.country == country,
            FxRateRecord.devise == devise,
        )
        return (await self._s.scalars(stmt)).first()

    async def upsert_taux(
        self, *, tenant_id: str, country: str, devise: str, taux_vers_xaf: Decimal, source: str
    ) -> FxRateRecord:
        """Saisir/mettre à jour un taux ⇒ retombe non validé (re-validation requise)."""
        rec = await self.get(tenant_id=tenant_id, country=country, devise=devise)
        if rec is None:
            rec = FxRateRecord(tenant_id=tenant_id, country=country, devise=devise)
            self._s.add(rec)
        rec.taux_vers_xaf = taux_vers_xaf
        rec.source = source
        rec.validated = False
        rec.validated_by = ""
        rec.validated_at = None
        await self._s.flush()
        return rec

    async def set_validation(
        self, *, tenant_id: str, country: str, devise: str, validated: bool, validated_by: str, note: str
    ) -> FxRateRecord | None:
        rec = await self.get(tenant_id=tenant_id, country=country, devise=devise)
        if rec is None:
            return None
        rec.validated = validated
        rec.validated_by = validated_by
        rec.note = note
        rec.validated_at = datetime.now(UTC) if validated else None
        await self._s.flush()
        return rec


class AssetRepository(_CrudRepo):
    model = AssetRecord


class EcheanceRepository(_CrudRepo):
    model = EcheanceRecord


class RisqueRepository(_CrudRepo):
    model = RisqueRecord


class IncidentRepository(_CrudRepo):
    model = IncidentRecord


class MarketingContactRepository(_CrudRepo):
    model = MarketingContactRecord


class CampaignRepository(_CrudRepo):
    model = CampaignRecord


class BankAccountRepository(_CrudRepo):
    model = BankAccountRecord


class CashFlowRepository(_CrudRepo):
    model = CashFlowRecord

    async def list(  # type: ignore[override]
        self,
        *,
        tenant_id: str,
        compte_code: str | None = None,
        statut: str | None = None,
    ) -> list[CashFlowRecord]:
        stmt = select(CashFlowRecord).where(CashFlowRecord.tenant_id == tenant_id)
        if compte_code is not None:
            stmt = stmt.where(CashFlowRecord.compte_code == compte_code)
        if statut is not None:
            stmt = stmt.where(CashFlowRecord.statut == statut)
        stmt = stmt.order_by(CashFlowRecord.date_operation.desc())
        return list(await self._s.scalars(stmt))


class ProjectRepository(_CrudRepo):
    model = ProjectRecord


class BudgetLineRepository(_CrudRepo):
    model = BudgetLineRecord

    async def list(  # type: ignore[override]
        self, *, tenant_id: str, project_id: str | None = None
    ) -> list[BudgetLineRecord]:
        stmt = select(BudgetLineRecord).where(BudgetLineRecord.tenant_id == tenant_id)
        if project_id is not None:
            stmt = stmt.where(BudgetLineRecord.project_id == project_id)
        return list(await self._s.scalars(stmt))


class MandateRepository(_CrudRepo):
    model = MandateRecord


class ResolutionRepository(_CrudRepo):
    model = ResolutionRecord


class EngagementRepository(_CrudRepo):
    model = EngagementRecord


class PurchaseBudgetRepository(_CrudRepo):
    model = PurchaseBudgetRecord

    async def upsert(
        self, *, tenant_id: str, direction: str, exercice: str, budget_xaf: Decimal
    ) -> PurchaseBudgetRecord:
        """Un seul budget par (direction, exercice) : met à jour ou crée."""
        stmt = select(PurchaseBudgetRecord).where(
            PurchaseBudgetRecord.tenant_id == tenant_id,
            PurchaseBudgetRecord.direction == direction,
            PurchaseBudgetRecord.exercice == exercice,
        )
        existing = (await self._s.scalars(stmt)).first()
        if existing is not None:
            existing.budget_xaf = budget_xaf
            await self._s.flush()
            return existing
        rec = PurchaseBudgetRecord(
            tenant_id=tenant_id, direction=direction, exercice=exercice, budget_xaf=budget_xaf
        )
        self._s.add(rec)
        await self._s.flush()
        return rec


class InteractionRepository(_CrudRepo):
    model = InteractionRecord

    async def list(  # type: ignore[override]
        self,
        *,
        tenant_id: str,
        customer_id: str | None = None,
        opportunity_id: str | None = None,
    ) -> list[Any]:
        stmt = select(InteractionRecord).where(InteractionRecord.tenant_id == tenant_id)
        if customer_id is not None:
            stmt = stmt.where(InteractionRecord.customer_id == customer_id)
        if opportunity_id is not None:
            stmt = stmt.where(InteractionRecord.opportunity_id == opportunity_id)
        stmt = stmt.order_by(InteractionRecord.date.desc())
        return list(await self._s.scalars(stmt))


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


class AgentFeedbackRepository:
    """Retour utilisateur sur les réponses d'agents (pouce ✓/✗ + correction)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, data: dict[str, Any]) -> AgentFeedbackRecord:
        """Persiste un nouveau feedback."""
        data.setdefault("created_at", datetime.now(UTC))
        rec = AgentFeedbackRecord(**data)
        self._s.add(rec)
        await self._s.flush()
        return rec

    async def list(
        self,
        *,
        tenant_id: str,
        agent: str | None = None,
        verdict: str | None = None,
        request_id: str | None = None,
    ) -> list[AgentFeedbackRecord]:
        """Liste les feedbacks avec filtres optionnels."""
        stmt = (
            select(AgentFeedbackRecord)
            .where(AgentFeedbackRecord.tenant_id == tenant_id)
            .order_by(AgentFeedbackRecord.created_at.desc())
        )
        if agent is not None:
            stmt = stmt.where(AgentFeedbackRecord.agent == agent)
        if verdict is not None:
            stmt = stmt.where(AgentFeedbackRecord.verdict == verdict)
        if request_id is not None:
            stmt = stmt.where(AgentFeedbackRecord.request_id == request_id)
        return list(await self._s.scalars(stmt))

    async def count_by_verdict(
        self,
        *,
        tenant_id: str,
        agent: str | None = None,
    ) -> dict[str, dict[str, int]]:
        """Compte le nombre de 'up' et 'down' par agent (stats).

        Retourne un dict ``{ agent: { "up": N, "down": N } }``.
        """
        stmt = (
            select(AgentFeedbackRecord.agent, AgentFeedbackRecord.verdict, func.count())
            .where(AgentFeedbackRecord.tenant_id == tenant_id)
            .group_by(AgentFeedbackRecord.agent, AgentFeedbackRecord.verdict)
        )
        if agent is not None:
            stmt = stmt.where(AgentFeedbackRecord.agent == agent)
        rows = (await self._s.execute(stmt)).all()
        stats: dict[str, dict[str, int]] = {}
        for ag, vd, cnt in rows:
            stats.setdefault(ag, {"up": 0, "down": 0})
            if vd in ("up", "down"):
                stats[ag][vd] = cnt
        return stats
