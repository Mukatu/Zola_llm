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


class EmployeeRecord(StoreBase):
    """Employé persisté (SIRH — registre du personnel)."""

    __tablename__ = "store_employees"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    matricule: Mapped[str] = mapped_column(String(32))
    nom_complet: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(4), default="NC")
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_embauche: Mapped[date] = mapped_column(Date)
    poste: Mapped[str] = mapped_column(String(120), default="")
    departement: Mapped[str] = mapped_column(String(120), default="")
    manager_matricule: Mapped[str | None] = mapped_column(String(32), nullable=True)
    categorie: Mapped[str | None] = mapped_column(String(40), nullable=True)
    code_emploi: Mapped[str | None] = mapped_column(String(32), nullable=True)
    salaire_base_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    quotite: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1"))
    statut: Mapped[str] = mapped_column(String(8), default="actif")
    date_sortie: Mapped[date | None] = mapped_column(Date, nullable=True)
    motif_sortie: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "matricule": self.matricule,
            "nom_complet": self.nom_complet,
            "genre": self.genre,
            "date_naissance": self.date_naissance.isoformat() if self.date_naissance else None,
            "date_embauche": self.date_embauche.isoformat() if self.date_embauche else None,
            "poste": self.poste,
            "departement": self.departement,
            "manager_matricule": self.manager_matricule,
            "categorie": self.categorie,
            "code_emploi": self.code_emploi,
            "salaire_base_xaf": str(self.salaire_base_xaf),
            "quotite": str(self.quotite),
            "statut": self.statut,
            "date_sortie": self.date_sortie.isoformat() if self.date_sortie else None,
            "motif_sortie": self.motif_sortie,
            "country": self.country,
        }


class ContractRecord(StoreBase):
    """Contrat de travail persisté (SIRH)."""

    __tablename__ = "store_contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(16), default="CDI")
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    fin_periode_essai: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="actif")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "employee_matricule": self.employee_matricule,
            "type": self.type,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "fin_periode_essai": (
                self.fin_periode_essai.isoformat() if self.fin_periode_essai else None
            ),
            "statut": self.statut,
        }


class AbsenceRecord(StoreBase):
    """Absence persistée (SIRH)."""

    __tablename__ = "store_absences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(16), default="conge_paye")
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date] = mapped_column(Date)
    jours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    statut: Mapped[str] = mapped_column(String(12), default="valide")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "employee_matricule": self.employee_matricule,
            "type": self.type,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "jours": str(self.jours),
            "statut": self.statut,
        }


class JobRoleRecord(StoreBase):
    """RME — Référentiel des emplois (emploi-repère)."""

    __tablename__ = "store_job_roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code_emploi: Mapped[str] = mapped_column(String(32))
    famille_professionnelle: Mapped[str] = mapped_column(String(120), default="")
    intitule: Mapped[str] = mapped_column(String(200))
    mission_principale: Mapped[str] = mapped_column(String(1000), default="")
    activites: Mapped[list[Any]] = mapped_column(JSON, default=list)
    kpis: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code_emploi": self.code_emploi,
            "famille_professionnelle": self.famille_professionnelle,
            "intitule": self.intitule,
            "mission_principale": self.mission_principale,
            "activites": self.activites,
            "kpis": self.kpis,
        }


class SkillRecord(StoreBase):
    """RMC — Cartographie des compétences (4 niveaux)."""

    __tablename__ = "store_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code_competence: Mapped[str] = mapped_column(String(32))
    domaine: Mapped[str] = mapped_column(String(20), default="technique")
    intitule: Mapped[str] = mapped_column(String(200))
    niveau_1: Mapped[str] = mapped_column(String(500), default="")
    niveau_2: Mapped[str] = mapped_column(String(500), default="")
    niveau_3: Mapped[str] = mapped_column(String(500), default="")
    niveau_4: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code_competence": self.code_competence,
            "domaine": self.domaine,
            "intitule": self.intitule,
            "niveau_1": self.niveau_1,
            "niveau_2": self.niveau_2,
            "niveau_3": self.niveau_3,
            "niveau_4": self.niveau_4,
        }


class RoleSkillRecord(StoreBase):
    """Profil de compétences requis par emploi (RME × RMC → niveau requis)."""

    __tablename__ = "store_role_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code_emploi: Mapped[str] = mapped_column(String(32))
    code_competence: Mapped[str] = mapped_column(String(32))
    niveau_requis: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code_emploi": self.code_emploi,
            "code_competence": self.code_competence,
            "niveau_requis": self.niveau_requis,
        }


class EmployeeSkillRecord(StoreBase):
    """Matrice opérationnelle : collaborateur × compétence → note 0-4."""

    __tablename__ = "store_employee_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    code_competence: Mapped[str] = mapped_column(String(32))
    note: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "employee_matricule": self.employee_matricule,
            "code_competence": self.code_competence,
            "note": self.note,
        }
