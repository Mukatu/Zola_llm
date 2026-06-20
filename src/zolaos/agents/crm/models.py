"""Modèles canoniques CRM / Commercial (addendum §3.2, CRM-1).

Clients/prospects, opportunités (pipeline), devis. `country` systématique
(multi-pays). Montants en Decimal (XAF).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Etape = Literal["prospection", "qualification", "proposition", "negociation", "gagnee", "perdue"]
StatutDevis = Literal["brouillon", "envoye", "accepte", "refuse", "expire"]


class Customer(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    id_externe: str
    nom: str
    type: Literal["client", "prospect"] = "prospect"
    email: str | None = None
    telephone: str | None = None
    secteur: str | None = None
    source: Literal["referral", "web", "salon", "appel", "autre"] = "autre"
    date_creation: date | None = None
    derniere_interaction: date | None = None
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class Opportunity(BaseModel):
    model_config = {"extra": "forbid"}

    id_externe: str
    client: str = Field(..., description="Nom ou id du client/prospect")
    libelle: str
    montant_xaf: Decimal = Field(..., ge=0)
    etape: Etape = "prospection"
    probabilite: Decimal | None = Field(default=None, ge=0, le=1, description="Si None, dérivée de l'étape")
    date_creation: date | None = None
    date_cloture_prevue: date | None = None
    derniere_interaction: date | None = None
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class QuoteLine(BaseModel):
    model_config = {"extra": "forbid"}

    libelle: str
    montant_ht_xaf: Decimal = Field(..., ge=0)


class Quote(BaseModel):
    """Devis — peut être converti en facture (Invoice) une fois accepté."""

    model_config = {"extra": "forbid"}

    id_externe: str
    numero: str
    client: str
    date_emission: date
    date_validite: date | None = None
    statut: StatutDevis = "brouillon"
    lignes: list[QuoteLine] = Field(default_factory=list)
    montant_ht_xaf: Decimal = Field(..., ge=0)
    montant_ttc_xaf: Decimal = Field(..., ge=0)
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")
