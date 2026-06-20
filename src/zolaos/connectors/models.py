"""Modèles canoniques ZolaOS pour le Connector Framework (V2.2 §2.4).

Schéma **normalisé** ZolaOS : peu importe le système source (Odoo, ERPNext,
Sage, CSV…), les connecteurs renvoient ces modèles. Le mapping déclaratif
(`mapping.py`) traduit `champ_source → champ_canonique` (ex: `full_name →
nom_complet`).

Multi-pays par tagging (directive §5.9) : chaque entité porte un `country`
ISO-2 (`cg` par défaut), jamais de constante pays en dur ailleurs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class CanonicalModel(BaseModel):
    """Base des modèles canoniques : country systématique + config stricte."""

    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    country: str = Field(default="cg", pattern=r"^[a-z]{2}$", description="ISO-3166-1 alpha-2")


class Employee(CanonicalModel):
    """Salarié normalisé (cible des connecteurs RH)."""

    id_externe: str = Field(..., description="Identifiant dans le système source")
    nom_complet: str
    poste: str | None = None
    matricule: str | None = None
    email: str | None = None
    date_embauche: date | None = None
    salaire_base_xaf: Decimal | None = Field(default=None, ge=0)
    actif: bool = True


class Invoice(CanonicalModel):
    """Facture normalisée (client ou fournisseur)."""

    id_externe: str
    numero: str
    sens: Literal["vente", "achat"] = "vente"
    tiers: str = Field(..., description="Nom du client (vente) ou fournisseur (achat)")
    date_emission: date
    date_echeance: date | None = None
    montant_ht_xaf: Decimal = Field(..., ge=0)
    montant_tva_xaf: Decimal | None = Field(default=None, ge=0)
    montant_ttc_xaf: Decimal = Field(..., ge=0)
    devise: str = Field(default="XAF", pattern=r"^[A-Z]{3}$")
    payee: bool = False


class JournalLine(BaseModel):
    """Ligne d'écriture comptable SYSCOHADA (un compte, un sens)."""

    model_config = {"extra": "forbid"}

    compte: str = Field(..., description="Numéro de compte SYSCOHADA")
    libelle: str
    debit_xaf: Decimal = Field(default=Decimal("0"), ge=0)
    credit_xaf: Decimal = Field(default=Decimal("0"), ge=0)


class JournalEntry(CanonicalModel):
    """Écriture comptable normalisée (push vers le système comptable)."""

    id_externe: str | None = None
    date_ecriture: date
    journal: str = Field(..., description="Code journal (ex: VT, AC, BQ, OD)")
    libelle: str
    reference: str | None = None
    lignes: list[JournalLine] = Field(..., min_length=1)

    def est_equilibree(self) -> bool:
        """Vrai si total débit == total crédit (invariant comptable)."""
        debit = sum((l.debit_xaf for l in self.lignes), Decimal("0"))
        credit = sum((l.credit_xaf for l in self.lignes), Decimal("0"))
        return debit == credit


class BankTransaction(CanonicalModel):
    """Mouvement bancaire/Mobile Money normalisé (cible des connecteurs Finance)."""

    id_externe: str
    date_operation: date
    libelle: str
    montant_xaf: Decimal = Field(..., description="Montant signé (négatif = débit)")
    sens: Literal["debit", "credit"]
    solde_xaf: Decimal | None = None
    compte: str | None = Field(default=None, description="Référence du compte/portefeuille")
    canal: Literal["bank", "momo", "airtel", "caisse", "autre"] = "bank"
