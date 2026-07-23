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

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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
    # Traçabilité multi-devise (MULTIDEV-2) : montant d'origine + taux appliqué à
    # l'écriture. Nuls quand la facture est déjà en XAF (les colonnes `_xaf`
    # restent la valeur canonique, normalisée, qu'exploite toute l'agrégation).
    montant_ht_devise: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    montant_ttc_devise: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    taux_applique: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
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
            "montant_ht_devise": (
                str(self.montant_ht_devise) if self.montant_ht_devise is not None else None
            ),
            "montant_ttc_devise": (
                str(self.montant_ttc_devise) if self.montant_ttc_devise is not None else None
            ),
            "taux_applique": str(self.taux_applique) if self.taux_applique is not None else None,
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
    pmp_xaf: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0")
    )  # coût moyen pondéré
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        valeur = self.quantite_actuelle * self.pmp_xaf
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
            "pmp_xaf": str(self.pmp_xaf),
            "valeur_stock_xaf": str(valeur.quantize(Decimal("0.01"))),
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StockMoveRecord(StoreBase):
    """Mouvement de stock (grand-livre des stocks) — entrée/sortie/ajustement/transfert.

    Le registre des mouvements transforme le stock d'une *photo* en *grand-livre*
    valorisé (PMP). La validation d'un mouvement met à jour l'article rattaché.
    """

    __tablename__ = "store_stock_moves"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    reference: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(
        String(12), default="entree"
    )  # entree|sortie|ajustement|transfert
    sku: Mapped[str] = mapped_column(String(64), index=True)
    quantite: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"))
    cout_unitaire_xaf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    valeur_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    emplacement: Mapped[str | None] = mapped_column(String(64), nullable=True)
    emplacement_dest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date_peremption: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")  # brouillon|valide
    motif: Mapped[str] = mapped_column(String(200), default="")
    date_mouvement: Mapped[date] = mapped_column(Date)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "reference": self.reference,
            "type": self.type,
            "sku": self.sku,
            "quantite": str(self.quantite),
            "cout_unitaire_xaf": (
                str(self.cout_unitaire_xaf) if self.cout_unitaire_xaf is not None else None
            ),
            "valeur_xaf": str(self.valeur_xaf),
            "emplacement": self.emplacement,
            "emplacement_dest": self.emplacement_dest,
            "lot": self.lot,
            "date_peremption": self.date_peremption.isoformat() if self.date_peremption else None,
            "statut": self.statut,
            "motif": self.motif,
            "date_mouvement": self.date_mouvement.isoformat() if self.date_mouvement else None,
            "country": self.country,
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
    # Champs déclaratifs (DAS 1 / CNSS — PAIE-3c)
    livret_cnss: Mapped[str | None] = mapped_column(String(32), nullable=True)
    n_contribuable: Mapped[str | None] = mapped_column(String(32), nullable=True)
    situation_matrimoniale: Mapped[str] = mapped_column(String(12), default="")  # CMVD
    nationalite: Mapped[str] = mapped_column(String(40), default="")
    nb_enfants: Mapped[int] = mapped_column(Integer, default=0)
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
            "livret_cnss": self.livret_cnss,
            "n_contribuable": self.n_contribuable,
            "situation_matrimoniale": self.situation_matrimoniale,
            "nationalite": self.nationalite,
            "nb_enfants": self.nb_enfants,
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


class VacancyRecord(StoreBase):
    """Vacance de poste / réquisition (recrutement)."""

    __tablename__ = "store_vacancies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code_vacance: Mapped[str] = mapped_column(String(32))
    code_emploi: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intitule: Mapped[str] = mapped_column(String(200))
    motif: Mapped[str] = mapped_column(String(20), default="creation")
    type_contrat_cible: Mapped[str] = mapped_column(String(16), default="CDI")
    nb_postes: Mapped[int] = mapped_column(Integer, default=1)
    departement: Mapped[str] = mapped_column(String(120), default="")
    lieu: Mapped[str] = mapped_column(String(120), default="")
    statut: Mapped[str] = mapped_column(String(16), default="ouverte")
    priorite: Mapped[str] = mapped_column(String(8), default="moyenne")
    date_ouverture: Mapped[date] = mapped_column(Date)
    date_cible: Mapped[date | None] = mapped_column(Date, nullable=True)
    manager_demandeur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    budget_xaf: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code_vacance": self.code_vacance,
            "code_emploi": self.code_emploi,
            "intitule": self.intitule,
            "motif": self.motif,
            "type_contrat_cible": self.type_contrat_cible,
            "nb_postes": self.nb_postes,
            "departement": self.departement,
            "lieu": self.lieu,
            "statut": self.statut,
            "priorite": self.priorite,
            "date_ouverture": self.date_ouverture.isoformat() if self.date_ouverture else None,
            "date_cible": self.date_cible.isoformat() if self.date_cible else None,
            "manager_demandeur": self.manager_demandeur,
            "budget_xaf": str(self.budget_xaf) if self.budget_xaf is not None else None,
        }


class CandidateRecord(StoreBase):
    """Candidat (vivier)."""

    __tablename__ = "store_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="spontanee")
    cv_uri: Mapped[str | None] = mapped_column(String(400), nullable=True)
    statut_vivier: Mapped[str] = mapped_column(String(12), default="actif")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "nom": self.nom,
            "prenom": self.prenom,
            "email": self.email,
            "telephone": self.telephone,
            "source": self.source,
            "cv_uri": self.cv_uri,
            "statut_vivier": self.statut_vivier,
        }


class ApplicationRecord(StoreBase):
    """Candidature = candidat × vacance (suivi pipeline)."""

    __tablename__ = "store_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    code_vacance: Mapped[str] = mapped_column(String(32), index=True)
    etape: Mapped[str] = mapped_column(String(16), default="reçue")
    date_candidature: Mapped[date] = mapped_column(Date)
    date_etape: Mapped[date | None] = mapped_column(Date, nullable=True)
    note_globale: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "candidate_id": self.candidate_id,
            "code_vacance": self.code_vacance,
            "etape": self.etape,
            "date_candidature": (
                self.date_candidature.isoformat() if self.date_candidature else None
            ),
            "date_etape": self.date_etape.isoformat() if self.date_etape else None,
            "note_globale": self.note_globale,
            "decision": self.decision,
        }


class InterviewRecord(StoreBase):
    """Entretien (grille structurée)."""

    __tablename__ = "store_interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    date_prevue: Mapped[date | None] = mapped_column(Date, nullable=True)
    type: Mapped[str] = mapped_column(String(16), default="RH")
    grille: Mapped[list[Any]] = mapped_column(JSON, default=list)
    score_global: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommandation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="planifie")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "application_id": self.application_id,
            "date_prevue": self.date_prevue.isoformat() if self.date_prevue else None,
            "type": self.type,
            "grille": self.grille,
            "score_global": self.score_global,
            "recommandation": self.recommandation,
            "statut": self.statut,
        }


class DocumentRecord(StoreBase):
    """Artefact généré persisté (transverse : RH, Droit, rapports…)."""

    __tablename__ = "store_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32), default="autre")
    metier: Mapped[str] = mapped_column(String(20), default="rh")
    titre: Mapped[str] = mapped_column(String(200))
    contenu: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "type": self.type,
            "metier": self.metier,
            "titre": self.titre,
            "contenu": self.contenu,
            "tags": self.tags,
            "source_ref": self.source_ref,
            "statut": self.statut,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TrainingRecord(StoreBase):
    """Catalogue de formation (SIRH-3)."""

    __tablename__ = "store_trainings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(32))
    intitule: Mapped[str] = mapped_column(String(200))
    competences_visees: Mapped[list[Any]] = mapped_column(JSON, default=list)
    modalite: Mapped[str] = mapped_column(String(20), default="presentiel")
    duree_heures: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    cout_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code": self.code,
            "intitule": self.intitule,
            "competences_visees": self.competences_visees,
            "modalite": self.modalite,
            "duree_heures": str(self.duree_heures),
            "cout_xaf": str(self.cout_xaf),
        }


class TrainingSessionRecord(StoreBase):
    """Session de formation planifiée."""

    __tablename__ = "store_training_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    training_code: Mapped[str] = mapped_column(String(32), index=True)
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    lieu: Mapped[str] = mapped_column(String(120), default="")
    formateur: Mapped[str] = mapped_column(String(120), default="")
    places: Mapped[int] = mapped_column(Integer, default=0)
    statut: Mapped[str] = mapped_column(String(12), default="planifiee")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "training_code": self.training_code,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "lieu": self.lieu,
            "formateur": self.formateur,
            "places": self.places,
            "statut": self.statut,
        }


class TrainingEnrollmentRecord(StoreBase):
    """Inscription d'un employé à une session."""

    __tablename__ = "store_training_enrollments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    statut: Mapped[str] = mapped_column(String(12), default="inscrit")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "employee_matricule": self.employee_matricule,
            "statut": self.statut,
        }


class TrainingEvaluationRecord(StoreBase):
    """Évaluation de formation (à chaud / à froid)."""

    __tablename__ = "store_training_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    enrollment_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(8), default="chaud")
    satisfaction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acquis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_eval: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "enrollment_id": self.enrollment_id,
            "type": self.type,
            "satisfaction": self.satisfaction,
            "acquis": self.acquis,
            "date_eval": self.date_eval.isoformat() if self.date_eval else None,
        }


class CustomerRecord(StoreBase):
    """Client / prospect persisté (CRM — P2b)."""

    __tablename__ = "store_customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    nom: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(12), default="prospect")  # client | prospect
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    secteur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(12), default="autre")
    date_creation: Mapped[date | None] = mapped_column(Date, nullable=True)
    derniere_interaction: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "nom": self.nom,
            "type": self.type,
            "email": self.email,
            "telephone": self.telephone,
            "secteur": self.secteur,
            "source": self.source,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "derniere_interaction": (
                self.derniere_interaction.isoformat() if self.derniere_interaction else None
            ),
            "country": self.country,
        }


class OpportunityRecord(StoreBase):
    """Opportunité commerciale persistée (pipeline — P2b)."""

    __tablename__ = "store_opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    client: Mapped[str] = mapped_column(String(200))
    libelle: Mapped[str] = mapped_column(String(200))
    montant_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    etape: Mapped[str] = mapped_column(String(16), default="prospection")
    probabilite: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    date_creation: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_cloture_prevue: Mapped[date | None] = mapped_column(Date, nullable=True)
    derniere_interaction: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "client": self.client,
            "libelle": self.libelle,
            "montant_xaf": str(self.montant_xaf),
            "etape": self.etape,
            "probabilite": str(self.probabilite) if self.probabilite is not None else None,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "date_cloture_prevue": (
                self.date_cloture_prevue.isoformat() if self.date_cloture_prevue else None
            ),
            "derniere_interaction": (
                self.derniere_interaction.isoformat() if self.derniere_interaction else None
            ),
            "country": self.country,
        }


class QuoteRecord(StoreBase):
    """Devis persisté (lignes en JSON) — convertible en facture (P2b)."""

    __tablename__ = "store_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    numero: Mapped[str] = mapped_column(String(64))
    client: Mapped[str] = mapped_column(String(200))
    date_emission: Mapped[date] = mapped_column(Date)
    date_validite: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")
    lignes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    montant_ht_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_ttc_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # si converti
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "numero": self.numero,
            "client": self.client,
            "date_emission": self.date_emission.isoformat() if self.date_emission else None,
            "date_validite": self.date_validite.isoformat() if self.date_validite else None,
            "statut": self.statut,
            "lignes": self.lignes,
            "montant_ht_xaf": str(self.montant_ht_xaf),
            "montant_ttc_xaf": str(self.montant_ttc_xaf),
            "invoice_id": self.invoice_id,
            "country": self.country,
        }


class InteractionRecord(StoreBase):
    """Interaction commerciale (journal des contacts — P2b enrichissement).

    Rattachée à un client et/ou une opportunité ; rend « dernière interaction »
    et les relances *réelles* dans le temps (au lieu d'un champ figé).
    """

    __tablename__ = "store_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    opportunity_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(12), default="note")  # appel|email|visite|relance|note
    date: Mapped[date] = mapped_column(Date)
    resume: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "opportunity_id": self.opportunity_id,
            "type": self.type,
            "date": self.date.isoformat() if self.date else None,
            "resume": self.resume,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SupplierRecord(StoreBase):
    """Fournisseur persisté (Achats / Procurement — P2c)."""

    __tablename__ = "store_suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    nom: Mapped[str] = mapped_column(String(200))
    secteur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note_qualite: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("0"))  # 0-5
    delai_moyen_jours: Mapped[int] = mapped_column(Integer, default=0)
    documents_conformite: Mapped[list[str]] = mapped_column(JSON, default=list)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "nom": self.nom,
            "secteur": self.secteur,
            "note_qualite": str(self.note_qualite),
            "delai_moyen_jours": self.delai_moyen_jours,
            "documents_conformite": self.documents_conformite,
            "actif": self.actif,
            "country": self.country,
        }


class PurchaseOrderRecord(StoreBase):
    """Bon de commande persisté (lignes JSON) — réceptionnable en facture d'achat (P2c)."""

    __tablename__ = "store_purchase_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    numero: Mapped[str] = mapped_column(String(64))
    fournisseur: Mapped[str] = mapped_column(String(200))
    objet: Mapped[str] = mapped_column(String(200), default="")
    date_emission: Mapped[date] = mapped_column(Date)
    # brouillon | envoye | confirme | receptionne
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")
    lignes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    montant_ht_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_ttc_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    delai_livraison_jours: Mapped[int] = mapped_column(Integer, default=0)
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # si réceptionné
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "numero": self.numero,
            "fournisseur": self.fournisseur,
            "objet": self.objet,
            "date_emission": self.date_emission.isoformat() if self.date_emission else None,
            "statut": self.statut,
            "lignes": self.lignes,
            "montant_ht_xaf": str(self.montant_ht_xaf),
            "montant_ttc_xaf": str(self.montant_ttc_xaf),
            "delai_livraison_jours": self.delai_livraison_jours,
            "invoice_id": self.invoice_id,
            "country": self.country,
        }


class BankAccountRecord(StoreBase):
    """Compte de trésorerie (banque / caisse / mobile money) — TRESO-1."""

    __tablename__ = "store_bank_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(32))
    libelle: Mapped[str] = mapped_column(String(120))
    banque: Mapped[str] = mapped_column(String(120), default="")
    type: Mapped[str] = mapped_column(String(16), default="banque")  # banque|caisse|mobile_money
    devise: Mapped[str] = mapped_column(String(3), default="XAF")
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    solde_initial_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code": self.code,
            "libelle": self.libelle,
            "banque": self.banque,
            "type": self.type,
            "devise": self.devise,
            "iban": self.iban,
            "solde_initial_xaf": str(self.solde_initial_xaf),
            "country": self.country,
        }


class CashFlowRecord(StoreBase):
    """Flux de trésorerie (encaissement/décaissement, réalisé ou prévu) — TRESO-1."""

    __tablename__ = "store_cash_flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    reference: Mapped[str] = mapped_column(String(64))
    compte_code: Mapped[str] = mapped_column(String(32), index=True)
    sens: Mapped[str] = mapped_column(
        String(13), default="encaissement"
    )  # encaissement|decaissement
    montant_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    date_operation: Mapped[date] = mapped_column(Date)
    date_prevue: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(8), default="realise")  # prevu|realise
    # workflow de validation des décaissements : "" | n1 | validee
    niveau_validation: Mapped[str] = mapped_column(String(8), default="")
    rapproche: Mapped[bool] = mapped_column(Boolean, default=False)
    categorie: Mapped[str] = mapped_column(String(60), default="")
    tiers: Mapped[str] = mapped_column(String(200), default="")
    libelle: Mapped[str] = mapped_column(String(200), default="")
    mode: Mapped[str] = mapped_column(String(16), default="virement")
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "reference": self.reference,
            "compte_code": self.compte_code,
            "sens": self.sens,
            "montant_xaf": str(self.montant_xaf),
            "date_operation": self.date_operation.isoformat() if self.date_operation else None,
            "date_prevue": self.date_prevue.isoformat() if self.date_prevue else None,
            "statut": self.statut,
            "niveau_validation": self.niveau_validation,
            "rapproche": self.rapproche,
            "categorie": self.categorie,
            "tiers": self.tiers,
            "libelle": self.libelle,
            "mode": self.mode,
            "invoice_id": self.invoice_id,
            "country": self.country,
        }


class EngagementRecord(StoreBase):
    """Engagement d'achat suivi sur la chaîne **EB → DA → BC** (Achats v2).

    Un enregistrement = un besoin suivi de bout en bout (Expression de Besoin →
    Demande d'Achat → Bon de Commande), avec dimension organisationnelle
    (direction/service/demandeur/acheteur) et suivi budgétaire (estimation vs
    montant engagé). Calqué sur l'outil métier réel des achats.
    """

    __tablename__ = "store_engagements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    numero_eb: Mapped[str] = mapped_column(String(32))
    numero_da: Mapped[str | None] = mapped_column(String(32), nullable=True)
    numero_bc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date_eb: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_da: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_bc: Mapped[date | None] = mapped_column(Date, nullable=True)
    direction: Mapped[str | None] = mapped_column(String(40), nullable=True)
    service: Mapped[str | None] = mapped_column(String(120), nullable=True)
    demandeur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    acheteur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fournisseur: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_besoin: Mapped[str] = mapped_column(Text, default="")
    description_da: Mapped[str] = mapped_column(Text, default="")
    description_bc: Mapped[str] = mapped_column(Text, default="")
    estimation_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    statut_ebda: Mapped[str] = mapped_column(String(40), default="")
    statut_bc: Mapped[str] = mapped_column(String(40), default="")
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "numero_eb": self.numero_eb,
            "numero_da": self.numero_da,
            "numero_bc": self.numero_bc,
            "date_eb": self.date_eb.isoformat() if self.date_eb else None,
            "date_da": self.date_da.isoformat() if self.date_da else None,
            "date_bc": self.date_bc.isoformat() if self.date_bc else None,
            "direction": self.direction,
            "service": self.service,
            "demandeur": self.demandeur,
            "acheteur": self.acheteur,
            "fournisseur": self.fournisseur,
            "description_besoin": self.description_besoin,
            "description_da": self.description_da,
            "description_bc": self.description_bc,
            "estimation_xaf": str(self.estimation_xaf),
            "montant_xaf": str(self.montant_xaf),
            "statut_ebda": self.statut_ebda,
            "statut_bc": self.statut_bc,
            "country": self.country,
        }


class PurchaseBudgetRecord(StoreBase):
    """Budget d'achats par direction et exercice (contrôle de gestion — pilotage)."""

    __tablename__ = "store_purchase_budgets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(40))
    exercice: Mapped[str] = mapped_column(String(8))  # ex. "2026"
    budget_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "direction": self.direction,
            "exercice": self.exercice,
            "budget_xaf": str(self.budget_xaf),
            "country": self.country,
        }


class AssetRecord(StoreBase):
    """Actif / équipement (Facility / Moyens généraux — OPS-1)."""

    __tablename__ = "store_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    libelle: Mapped[str] = mapped_column(String(200))
    type_actif: Mapped[str] = mapped_column(String(20), default="autre")
    maintenance_intervalle_jours: Mapped[int] = mapped_column(Integer, default=0)
    derniere_maintenance: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "libelle": self.libelle,
            "type_actif": self.type_actif,
            "maintenance_intervalle_jours": self.maintenance_intervalle_jours,
            "derniere_maintenance": (
                self.derniere_maintenance.isoformat() if self.derniere_maintenance else None
            ),
            "country": self.country,
        }


class EcheanceRecord(StoreBase):
    """Échéance (assurance, contrôle réglementaire, contrat…) — Facility, OPS-1."""

    __tablename__ = "store_echeances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type_echeance: Mapped[str] = mapped_column(String(20), default="autre")
    libelle: Mapped[str] = mapped_column(String(200))
    date_echeance: Mapped[date] = mapped_column(Date)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "asset_id": self.asset_id,
            "type_echeance": self.type_echeance,
            "libelle": self.libelle,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "country": self.country,
        }


class RisqueRecord(StoreBase):
    """Risque HSE (probabilité × gravité → criticité) — OPS-1."""

    __tablename__ = "store_risques"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    libelle: Mapped[str] = mapped_column(String(200))
    probabilite: Mapped[int] = mapped_column(Integer, default=1)  # 1-5
    gravite: Mapped[int] = mapped_column(Integer, default=1)  # 1-5
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "libelle": self.libelle,
            "probabilite": self.probabilite,
            "gravite": self.gravite,
            "country": self.country,
        }


class ProjectRecord(StoreBase):
    """Projet financé par bailleur (Projets ONG)."""

    __tablename__ = "store_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    intitule: Mapped[str] = mapped_column(String(200))
    bailleur: Mapped[str] = mapped_column(String(200))
    convention_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    devise: Mapped[str] = mapped_column(String(3), default="XAF")
    budget_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    date_debut: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut: Mapped[str] = mapped_column(String(20), default="en_cours")  # en_cours|clos|suspendu
    responsable: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "intitule": self.intitule,
            "bailleur": self.bailleur,
            "convention_ref": self.convention_ref,
            "devise": self.devise,
            "budget_total": str(self.budget_total),
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "statut": self.statut,
            "responsable": self.responsable,
            "country": self.country,
        }


class BudgetLineRecord(StoreBase):
    """Ligne budgétaire d'un projet (rubrique × activité) — Projets ONG."""

    __tablename__ = "store_budget_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    rubrique: Mapped[str] = mapped_column(String(120))
    activite: Mapped[str | None] = mapped_column(String(200), nullable=True)
    montant_prevu: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_engage: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_realise: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "rubrique": self.rubrique,
            "activite": self.activite,
            "montant_prevu": str(self.montant_prevu),
            "montant_engage": str(self.montant_engage),
            "montant_realise": str(self.montant_realise),
            "eligible": self.eligible,
        }


class MandateRecord(StoreBase):
    """Mandat social (registre) — Secrétariat sociétaire (OPS-4)."""

    __tablename__ = "store_mandates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    titulaire: Mapped[str] = mapped_column(String(120))
    fonction: Mapped[str] = mapped_column(String(60), default="autre")
    date_nomination: Mapped[date] = mapped_column(Date)
    duree_annees: Mapped[int] = mapped_column(Integer, default=0)  # 0 = durée indéterminée
    organe: Mapped[str | None] = mapped_column(String(40), nullable=True)  # gerance|conseil|...
    statut: Mapped[str] = mapped_column(String(20), default="actif")  # actif|expire|revoque
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "titulaire": self.titulaire,
            "fonction": self.fonction,
            "date_nomination": self.date_nomination.isoformat() if self.date_nomination else None,
            "duree_annees": self.duree_annees,
            "organe": self.organe,
            "statut": self.statut,
            "country": self.country,
        }


class ResolutionRecord(StoreBase):
    """Résolution d'assemblée/conseil (AG/CA) — Secrétariat sociétaire (OPS-4)."""

    __tablename__ = "store_resolutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    type_reunion: Mapped[str] = mapped_column(String(8))  # AGO|AGE|CA
    date_reunion: Mapped[date] = mapped_column(Date)
    objet: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(Text, default="")
    reference_pv: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quorum: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "type_reunion": self.type_reunion,
            "date_reunion": self.date_reunion.isoformat() if self.date_reunion else None,
            "objet": self.objet,
            "decision": self.decision,
            "reference_pv": self.reference_pv,
            "quorum": self.quorum,
            "country": self.country,
        }


class IncidentRecord(StoreBase):
    """Incident HSE (accident, presqu'accident…) — OPS-1."""

    __tablename__ = "store_incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    date_incident: Mapped[date] = mapped_column(Date)
    type_incident: Mapped[str] = mapped_column(String(20), default="autre")
    gravite: Mapped[str] = mapped_column(String(12), default="mineur")
    description: Mapped[str] = mapped_column(Text, default="")
    jours_arret: Mapped[int] = mapped_column(Integer, default=0)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "date_incident": self.date_incident.isoformat() if self.date_incident else None,
            "type_incident": self.type_incident,
            "gravite": self.gravite,
            "description": self.description,
            "jours_arret": self.jours_arret,
            "country": self.country,
        }


class MarketingContactRecord(StoreBase):
    """Contact marketing persisté — **consentement & finalités** (Loi 29-2019, MKT-1)."""

    __tablename__ = "store_marketing_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    id_externe: Mapped[str] = mapped_column(String(64))
    nom: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    secteur: Mapped[str | None] = mapped_column(String(120), nullable=True)
    type: Mapped[str] = mapped_column(String(12), default="prospect")  # client | prospect
    derniere_interaction: Mapped[date | None] = mapped_column(Date, nullable=True)
    consentement_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    finalites: Mapped[list[str]] = mapped_column(JSON, default=list)
    date_consentement: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "id_externe": self.id_externe,
            "nom": self.nom,
            "email": self.email,
            "telephone": self.telephone,
            "secteur": self.secteur,
            "type": self.type,
            "derniere_interaction": (
                self.derniere_interaction.isoformat() if self.derniere_interaction else None
            ),
            "consentement_marketing": self.consentement_marketing,
            "finalites": self.finalites,
            "date_consentement": (
                self.date_consentement.isoformat() if self.date_consentement else None
            ),
            "source": self.source,
            "country": self.country,
        }


class CampaignRecord(StoreBase):
    """Campagne marketing persistée (canal, finalité, statut, métriques) — MKT-1."""

    __tablename__ = "store_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    nom: Mapped[str] = mapped_column(String(120))
    canal: Mapped[str] = mapped_column(String(8), default="email")  # email | sms | post
    finalite: Mapped[str] = mapped_column(String(60))
    segment: Mapped[str | None] = mapped_column(String(60), nullable=True)
    objet: Mapped[str | None] = mapped_column(String(200), nullable=True)
    statut: Mapped[str] = mapped_column(
        String(12), default="brouillon"
    )  # brouillon|validee|envoyee
    date_creation: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_envoi: Mapped[date | None] = mapped_column(Date, nullable=True)
    nb_cibles: Mapped[int] = mapped_column(Integer, default=0)
    nb_envois: Mapped[int] = mapped_column(Integer, default=0)
    nb_ouvertures: Mapped[int] = mapped_column(Integer, default=0)
    nb_clics: Mapped[int] = mapped_column(Integer, default=0)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "nom": self.nom,
            "canal": self.canal,
            "finalite": self.finalite,
            "segment": self.segment,
            "objet": self.objet,
            "statut": self.statut,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "date_envoi": self.date_envoi.isoformat() if self.date_envoi else None,
            "nb_cibles": self.nb_cibles,
            "nb_envois": self.nb_envois,
            "nb_ouvertures": self.nb_ouvertures,
            "nb_clics": self.nb_clics,
            "country": self.country,
        }


class PayslipRecord(StoreBase):
    """Bulletin de paie historisé (résultat du moteur paie) — PAIE-1."""

    __tablename__ = "store_payslips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    periode: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    brut_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    cotisations_salariales: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    total_cotisations_salariales_xaf: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0")
    )
    base_imposable_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    irpp_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    # Rubriques déclaratives DAS 1 (PAIE-3e) — montants déclarés, défaut 0
    avantages_nature_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    indemnites_non_imposables_xaf: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0")
    )
    # Rubriques de paie paramétrables appliquées (code → montant signé) — PAIE-6b
    rubriques: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    net_a_payer_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    cotisations_patronales: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cout_employeur_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")  # brouillon | valide
    date_paiement: Mapped[date | None] = mapped_column(Date, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "employee_matricule": self.employee_matricule,
            "periode": self.periode,
            "brut_xaf": str(self.brut_xaf),
            "cotisations_salariales": self.cotisations_salariales,
            "total_cotisations_salariales_xaf": str(self.total_cotisations_salariales_xaf),
            "base_imposable_xaf": str(self.base_imposable_xaf),
            "irpp_xaf": str(self.irpp_xaf),
            "avantages_nature_xaf": str(self.avantages_nature_xaf),
            "indemnites_non_imposables_xaf": str(self.indemnites_non_imposables_xaf),
            "rubriques": self.rubriques,
            "net_a_payer_xaf": str(self.net_a_payer_xaf),
            "cotisations_patronales": self.cotisations_patronales,
            "cout_employeur_xaf": str(self.cout_employeur_xaf),
            "statut": self.statut,
            "date_paiement": self.date_paiement.isoformat() if self.date_paiement else None,
            "country": self.country,
        }


class PayslipArchiveRecord(StoreBase):
    """Bulletin archivé (coffre-fort) — instantané immuable + rendu HTML (PAIE-10)."""

    __tablename__ = "store_payslip_archives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    periode: Mapped[str] = mapped_column(String(7), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    html: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "employee_matricule": self.employee_matricule,
            "periode": self.periode,
            "net_a_payer_xaf": self.snapshot.get("net_a_payer_xaf"),
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


class PayrollVariableRecord(StoreBase):
    """Variables de paie d'un salarié pour une période (PAIE-8).

    `payload` : heures supplémentaires, primes et retenues ponctuelles du mois.
    Converties en rubriques ad hoc à l'émission du bulletin de la période.
    """

    __tablename__ = "store_payroll_variables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    periode: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "employee_matricule": self.employee_matricule,
            "periode": self.periode,
            "payload": self.payload,
        }


class PayslipTemplateRecord(StoreBase):
    """Modèle de bulletin de paie personnalisé par tenant (PAIE-7a).

    `payload` : configuration structurée (titre, logo, couleur, mentions, options
    d'affichage). Le bulletin est assemblé à partir de ce modèle + des données du
    bulletin + de l'identité employeur (config tenant).
    """

    __tablename__ = "store_payslip_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "tenant_id": self.tenant_id, "payload": self.payload}


class EmployeeRubriqueRecord(StoreBase):
    """Affectation d'une rubrique de paie à un salarié (avec montant facultatif) — PAIE-6c.

    Référence une rubrique du barème par son `code` ; `valeur` (si non nulle)
    surcharge la valeur du barème pour ce salarié.
    """

    __tablename__ = "store_employee_rubriques"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(40))
    valeur: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "employee_matricule": self.employee_matricule,
            "code": self.code,
            "valeur": str(self.valeur) if self.valeur is not None else None,
        }


class PayrollScaleRecord(StoreBase):
    """Barème de paie édité et persisté par tenant (override de la graine) — PAIE-6a.

    Le fichier `ref/payroll_<pays>.json` reste la graine par défaut ; dès qu'un
    tenant édite son barème, le `payload` (structure complète du barème) prévaut.
    Chaque édition porte une nouvelle `version` ⇒ la validation experte retombe.
    """

    __tablename__ = "store_payroll_scales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    version: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "country": self.country,
            "version": self.version,
            "payload": self.payload,
        }


class PayrollScaleValidationRecord(StoreBase):
    """Validation experte d'un barème de paie (lève le verrou) — PAIE-5.

    Décision de conformité par (tenant, pays, version) : tant qu'aucune validation
    n'existe pour la version courante, l'émission de bulletin définitif reste
    refusée. Changer la version du barème invalide automatiquement la décision.
    """

    __tablename__ = "store_payroll_validations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    version: Mapped[str] = mapped_column(String(64))
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "country": self.country,
            "version": self.version,
            "validated": self.validated,
            "validated_by": self.validated_by,
            "note": self.note,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
        }


class FxRateRecord(StoreBase):
    """Taux de change gouverné (override tenant) — MULTIDEV-1.

    Une ligne par (tenant, pays, devise). ``taux_vers_xaf`` = valeur d'une unité
    de ``devise`` en XAF. La graine `ref/fx_rates_<pays>.json` fournit les
    valeurs par défaut ; dès qu'un tenant saisit un taux, cette ligne prévaut.
    Chaque édition remet ``validated`` à false (re-validation experte requise).
    """

    __tablename__ = "store_fx_rates"
    __table_args__ = (UniqueConstraint("tenant_id", "country", "devise", name="uq_fx_rate"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    devise: Mapped[str] = mapped_column(String(3))
    taux_vers_xaf: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "country": self.country,
            "devise": self.devise,
            "taux_vers_xaf": (
                str(self.taux_vers_xaf) if self.taux_vers_xaf is not None else None
            ),
            "validated": self.validated,
            "validated_by": self.validated_by,
            "source": self.source,
            "note": self.note,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
        }


class EvaluationRecord(StoreBase):
    """Évaluation annuelle : performance × potentiel (SIRH-3b)."""

    __tablename__ = "store_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    employee_matricule: Mapped[str] = mapped_column(String(32), index=True)
    periode: Mapped[str] = mapped_column(String(16), default="")
    performance: Mapped[int] = mapped_column(Integer, default=3)
    potentiel: Mapped[int] = mapped_column(Integer, default=3)
    objectifs: Mapped[str] = mapped_column(Text, default="")
    commentaire: Mapped[str] = mapped_column(Text, default="")
    statut: Mapped[str] = mapped_column(String(12), default="brouillon")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "employee_matricule": self.employee_matricule,
            "periode": self.periode,
            "performance": self.performance,
            "potentiel": self.potentiel,
            "objectifs": self.objectifs,
            "commentaire": self.commentaire,
            "statut": self.statut,
        }


class AgentFeedbackRecord(StoreBase):
    """Retour utilisateur sur une réponse d'agent (pouce ✓/✗ + correction experte).

    Socle de l'auto-amélioration : capture le verdict, la correction éventuelle et
    un instantané du contexte RAG (citations/chunks) au moment de la réponse.
    """

    __tablename__ = "store_agent_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="local")
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    agent: Mapped[str] = mapped_column(String(64))  # ex : "legal.ohada", "sante.pharma"
    query: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(4))  # "up" | "down"
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Marqueur local d'idempotence de la contribution (niveau 3) — reste chez le
    # locataire, sans effet sur l'anonymat du candidat émis.
    contributed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "agent": self.agent,
            "query": self.query,
            "response": self.response,
            "verdict": self.verdict,
            "correction": self.correction,
            "context_snapshot": self.context_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ContributionOptin(StoreBase):
    """Consentement d'un locataire à contribuer au moteur commun (niveau 3).

    **Désactivé par défaut**, par périmètre (poles/modules autorisés), révocable.
    Local au déploiement — c'est la porte que seul le client ouvre.
    """

    __tablename__ = "store_contribution_optin"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, default="local")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)  # poles/modules autorisés
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "enabled": self.enabled,
            "scopes": list(self.scopes or []),
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ContribCandidate(StoreBase):
    """Candidat de contribution en **quarantaine** — dérivé, anonymisé, non promu.

    **Aucun `tenant_id`, aucun lien source** : anonymat par construction (I1/I6).
    L'anonymisation a lieu AVANT l'insertion (I2). `content_hash` sert la déduplication
    et le compteur de corroboration (k-anonymat, I3). Rien n'entre dans le moteur
    sans validation humaine (I5) — géré en Phase B.
    """

    __tablename__ = "store_contrib_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(24))  # qa | correction | terminologie | categorisation
    domaine: Mapped[str] = mapped_column(
        String(64), default=""
    )  # pôle/agent (catégorie, non privé)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # assaini
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Empreintes d'origine **anonymes** (locataires distincts) → k-anonymat (I3).
    # Ne contient jamais de tenant_id ; sert uniquement au comptage de corroboration.
    origins: Mapped[list[str]] = mapped_column(JSON, default=list)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)  # = nb d'origines distinctes
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|validated|rejected
    validated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "domaine": self.domaine,
            "payload": dict(self.payload or {}),
            "occurrences": self.occurrences,
            "status": self.status,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
        }


class LearnedRule(StoreBase):
    """Règle **apprise** déterministe, promue depuis le communs (niveau 3).

    Générique et **multi-métier** : `(domaine, cle) -> valeur`. Ex. compta :
    domaine ``erp.compta``, cle = libellé normalisé anonymisé, valeur = compte
    SYSCOHADA. Consultée en amont des moteurs déterministes (override explicable).
    Anonyme : la `cle` est passée par la rédaction PII avant promotion.
    """

    __tablename__ = "store_learned_rules"
    __table_args__ = (UniqueConstraint("domaine", "cle", name="uq_learned_domaine_cle"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    domaine: Mapped[str] = mapped_column(String(64), index=True)
    cle: Mapped[str] = mapped_column(String(300))
    valeur: Mapped[str] = mapped_column(String(120))
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    validated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    promoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domaine": self.domaine,
            "cle": self.cle,
            "valeur": self.valeur,
            "occurrences": self.occurrences,
        }


class CommonsAudit(StoreBase):
    """Journal **anonyme** des promotions vers le moteur (I6).

    Trace ce qui est entré dans le communs : empreinte de contenu, cible,
    validateur, date. **Aucune référence locataire.**
    """

    __tablename__ = "store_commons_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(24))  # rag_commons | learned_rules
    domaine: Mapped[str] = mapped_column(String(64), default="")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    promoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CreditApplicationRecord(StoreBase):
    """Dossier de crédit persisté (score figé + workflow d'octroi) — FINTECH-3.

    On stocke l'instantané du dossier (`dossier`) et du résultat de scoring
    (`resultat` : facteurs + avertissements) au moment de l'évaluation, plus les
    champs saillants pour le pilotage. Le `statut` porte la décision humaine, la
    `decision` reste la recommandation déterministe du moteur.
    """

    __tablename__ = "store_credit_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    numero: Mapped[str] = mapped_column(String(64))
    client: Mapped[str] = mapped_column(String(200))
    montant_demande_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    duree_mois: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(2), default="E")
    decision: Mapped[str] = mapped_column(String(12), default="refuse")  # recommandation moteur
    # evaluee | accordee | refusee | decaissee | cloturee (décision/suivi humain)
    statut: Mapped[str] = mapped_column(String(16), default="evaluee")
    date_decaissement: Mapped[date | None] = mapped_column(Date, nullable=True)
    taux_endettement_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    mensualite_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_max_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    dossier: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resultat: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "numero": self.numero,
            "client": self.client,
            "montant_demande_xaf": str(self.montant_demande_xaf),
            "duree_mois": self.duree_mois,
            "score": self.score,
            "grade": self.grade,
            "decision": self.decision,
            "statut": self.statut,
            "date_decaissement": (
                self.date_decaissement.isoformat() if self.date_decaissement else None
            ),
            "taux_endettement_pct": str(self.taux_endettement_pct),
            "mensualite_xaf": str(self.mensualite_xaf),
            "montant_max_xaf": str(self.montant_max_xaf),
            "dossier": self.dossier,
            "resultat": self.resultat,
            "commentaire": self.commentaire,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KycRecordRecord(StoreBase):
    """Registre KYC persisté (évaluation figée + décision) — FINTECH-3."""

    __tablename__ = "store_kyc_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    nom: Mapped[str] = mapped_column(String(200))
    type_client: Mapped[str] = mapped_column(String(16), default="particulier")
    niveau_risque: Mapped[str] = mapped_column(String(8), default="faible")
    score_risque: Mapped[int] = mapped_column(Integer, default=0)
    vigilance: Mapped[str] = mapped_column(String(12), default="standard")
    complet: Mapped[bool] = mapped_column(Boolean, default=False)
    peut_entrer_en_relation: Mapped[bool] = mapped_column(Boolean, default=False)
    pep: Mapped[bool] = mapped_column(Boolean, default=False)
    # a_valider | valide | refuse (décision conformité)
    statut: Mapped[str] = mapped_column(String(16), default="a_valider")
    profil: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resultat: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    commentaire: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="cg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "nom": self.nom,
            "type_client": self.type_client,
            "niveau_risque": self.niveau_risque,
            "score_risque": self.score_risque,
            "vigilance": self.vigilance,
            "complet": self.complet,
            "peut_entrer_en_relation": self.peut_entrer_en_relation,
            "pep": self.pep,
            "statut": self.statut,
            "profil": self.profil,
            "resultat": self.resultat,
            "commentaire": self.commentaire,
            "country": self.country,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LoanInstallmentRecord(StoreBase):
    """Échéance d'un prêt décaissé (échéancier de remboursement) — FINTECH-6.

    Rattachée à un dossier de crédit (`application_id`). `statut` porte le suivi de
    paiement (a_venir | partiel | paye) ; le retard est **dérivé** à la lecture
    (date d'échéance passée + solde non nul) pour rester juste dans le temps.
    """

    __tablename__ = "store_loan_installments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    application_id: Mapped[str] = mapped_column(String(36), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    date_echeance: Mapped[date] = mapped_column(Date)
    principal_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    interet_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    montant_paye_xaf: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    statut: Mapped[str] = mapped_column(String(12), default="a_venir")  # a_venir|partiel|paye
    paye_le: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    def to_dict(self) -> dict[str, Any]:
        reste = self.montant_xaf - self.montant_paye_xaf
        en_retard = self.statut != "paye" and reste > 0 and self.date_echeance < _now().date()
        return {
            "id": self.id,
            "application_id": self.application_id,
            "numero": self.numero,
            "date_echeance": self.date_echeance.isoformat() if self.date_echeance else None,
            "principal_xaf": str(self.principal_xaf),
            "interet_xaf": str(self.interet_xaf),
            "montant_xaf": str(self.montant_xaf),
            "montant_paye_xaf": str(self.montant_paye_xaf),
            "reste_xaf": str(reste),
            "statut": self.statut,
            "en_retard": en_retard,
            "paye_le": self.paye_le.isoformat() if self.paye_le else None,
        }
