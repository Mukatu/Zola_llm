"""Système de référence léger (persistance) — addendum persistance légère.

Base de métadonnées **dédiée** (`StoreBase`), distincte du cœur (`core`), pour
un système de référence scopé : on stocke les entités que les moteurs
déterministes manipulent déjà (ici : Factures). Multi-tenant (`tenant_id`),
horodaté, compatible PostgreSQL (prod) ET SQLite (tests).

Tables préfixées `store_*`. Schéma `store` géré en migration côté PostgreSQL ;
ici on reste sur la metadata pour rester portable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class StoreBase(DeclarativeBase):
    """Base ORM du système de référence léger (séparée du cœur)."""


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class InvoiceRecord(StoreBase):
    """Facture persistée (client/fournisseur)."""

    __tablename__ = "store_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    numero: Mapped[str] = mapped_column(String(64))
    sens: Mapped[str] = mapped_column(String(8), default="vente")  # vente | achat
    tiers: Mapped[str] = mapped_column(String(200))
    date_emission: Mapped[date] = mapped_column(Date)
    date_echeance: Mapped[date | None] = mapped_column(Date, nullable=True)
    montant_ht_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_tva_xaf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    montant_ttc_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    devise: Mapped[str] = mapped_column(String(3), default="XAF")
    payee: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "numero": self.numero,
            "sens": self.sens,
            "tiers": self.tiers,
            "date_emission": self.date_emission.isoformat() if self.date_emission else None,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "montant_ht_xaf": str(self.montant_ht_xaf),
            "montant_tva_xaf": (
                str(self.montant_tva_xaf) if self.montant_tva_xaf is not None else None
            ),
            "montant_ttc_xaf": str(self.montant_ttc_xaf),
            "devise": self.devise,
            "payee": self.payee,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JournalEntryRecord(StoreBase):
    """Écriture comptable persistée (lignes en JSON)."""

    __tablename__ = "store_journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    date_ecriture: Mapped[date] = mapped_column(Date)
    journal: Mapped[str] = mapped_column(String(16), default="OD")
    libelle: Mapped[str] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lignes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    total_debit_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    total_credit_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    equilibre: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "date_ecriture": self.date_ecriture.isoformat() if self.date_ecriture else None,
            "journal": self.journal,
            "libelle": self.libelle,
            "reference": self.reference,
            "lignes": self.lignes,
            "total_debit_xaf": str(self.total_debit_xaf),
            "total_credit_xaf": str(self.total_credit_xaf),
            "equilibre": self.equilibre,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StockItemRecord(StoreBase):
    """Article de stock persisté (système de référence léger)."""

    __tablename__ = "store_stock_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(64))
    libelle: Mapped[str] = mapped_column(String(200))
    quantite_actuelle: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    unite: Mapped[str] = mapped_column(String(16), default="unité")
    conso_moyenne_jour: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    delai_appro_jours: Mapped[int] = mapped_column(Integer, default=0)
    stock_securite: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "sku": self.sku,
            "libelle": self.libelle,
            "quantite_actuelle": str(self.quantite_actuelle),
            "unite": self.unite,
            "conso_moyenne_jour": str(self.conso_moyenne_jour),
            "delai_appro_jours": self.delai_appro_jours,
            "stock_securite": str(self.stock_securite),
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
