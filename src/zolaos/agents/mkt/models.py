"""Modèles Marketing (addendum §3.3, MKT-1).

`MarketingContact` porte le **consentement** et les **finalités** (Loi 29-2019
sur les données personnelles — privacy by design).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MarketingContact(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    id_externe: str
    nom: str
    email: str | None = None
    secteur: str | None = None
    type: Literal["client", "prospect"] = "prospect"
    derniere_interaction: date | None = None
    # Conformité Loi 29-2019 :
    consentement_marketing: bool = False
    finalites: list[str] = Field(default_factory=list, description="Finalités consenties (ex: 'newsletter', 'promotions')")
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")


class Campaign(BaseModel):
    model_config = {"extra": "forbid"}

    nom: str
    canal: Literal["email", "sms", "post"] = "email"
    finalite: str = Field(..., description="Finalité de la campagne (doit être consentie par la cible)")
    segment_nom: str | None = None
    objet: str | None = None
