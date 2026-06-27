"""Endpoint déterministe Marketing (FE↔BE) — segmentation + consentement.

Profil box. Privacy by design (Loi 29-2019) : l'audience éligible est calculée
**en code** (consentement + finalité) ; la génération de contenu passe par
l'agent via /v1/query, mais seulement sur une audience consentante.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.mkt.consent import consent_summary, filter_consented
from zolaos.agents.mkt.models import MarketingContact
from zolaos.agents.mkt.segmentation import segment_contacts
from zolaos.db.session import get_session
from zolaos.db.store_repo import CampaignRepository, MarketingContactRepository

router = APIRouter(prefix="/v1/mkt", tags=["marketing"])


class MktAudienceRequest(BaseModel):
    contacts: list[MarketingContact] = Field(default_factory=list)
    finalite: str


@router.post("/audience", summary="Segmentation + audience consentante (déterministe, Loi 29-2019)")
def mkt_audience(req: MktAudienceRequest) -> dict[str, Any]:
    seg = segment_contacts(req.contacts)
    return {
        "segments": {k: len(v) for k, v in seg.items()},
        "consent": asdict(consent_summary(req.contacts, req.finalite)),
    }


# ----------------------------------------------------------------- registre persisté (MKT-1)


class ContactIn(BaseModel):
    id_externe: str
    nom: str
    email: str | None = None
    telephone: str | None = None
    secteur: str | None = None
    type: str = "prospect"
    derniere_interaction: date | None = None
    consentement_marketing: bool = False
    finalites: list[str] = Field(default_factory=list)
    date_consentement: date | None = None
    source: str | None = None
    country: str = "cg"


class ContactPatch(BaseModel):
    nom: str | None = None
    email: str | None = None
    secteur: str | None = None
    type: str | None = None
    consentement_marketing: bool | None = None
    finalites: list[str] | None = None
    date_consentement: date | None = None


class CampaignIn(BaseModel):
    nom: str
    canal: str = "email"
    finalite: str
    segment: str | None = None
    objet: str | None = None
    date_creation: date | None = None
    country: str = "cg"


def _contact_of(rec: Any) -> MarketingContact:
    return MarketingContact(
        id_externe=rec.id_externe,
        nom=rec.nom,
        email=rec.email,
        secteur=rec.secteur,
        type=rec.type if rec.type in ("client", "prospect") else "prospect",
        derniere_interaction=rec.derniere_interaction,
        consentement_marketing=rec.consentement_marketing,
        finalites=list(rec.finalites or []),
        country=rec.country,
    )


@router.post("/contacts", status_code=status.HTTP_201_CREATED, summary="Créer un contact")
async def create_contact(
    body: ContactIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await MarketingContactRepository(session).create(
        {**body.model_dump(), "tenant_id": tenant_id}
    )
    await session.commit()
    return rec.to_dict()


@router.get("/contacts", summary="Lister les contacts")
async def list_contacts(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await MarketingContactRepository(session).list(tenant_id=tenant_id)
    return {"contacts": [r.to_dict() for r in rows]}


@router.patch("/contacts/{contact_id}", summary="Mettre à jour un contact (consentement inclus)")
async def patch_contact(
    contact_id: str,
    body: ContactPatch,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rec = await MarketingContactRepository(session).update(
        contact_id, tenant_id=tenant_id, fields=body.model_dump(exclude_none=True)
    )
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contact_not_found")
    await session.commit()
    return rec.to_dict()


@router.delete("/contacts/{contact_id}", summary="Supprimer un contact")
async def delete_contact(
    contact_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await MarketingContactRepository(session).delete(contact_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contact_not_found")
    await session.commit()
    return {"deleted": contact_id}


@router.get("/audience-store", summary="Audience consentante sur le registre (par finalité)")
async def audience_store(
    finalite: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = await MarketingContactRepository(session).list(tenant_id=tenant_id)
    contacts = [_contact_of(r) for r in rows]
    seg = segment_contacts(contacts)
    return {
        "finalite": finalite,
        "segments": {k: len(v) for k, v in seg.items()},
        "consent": asdict(consent_summary(contacts, finalite)),
    }


@router.post("/campaigns", status_code=status.HTTP_201_CREATED, summary="Créer une campagne")
async def create_campaign(
    body: CampaignIn, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rec = await CampaignRepository(session).create({**body.model_dump(), "tenant_id": tenant_id})
    await session.commit()
    return rec.to_dict()


@router.get("/campaigns", summary="Lister les campagnes")
async def list_campaigns(
    tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    rows = await CampaignRepository(session).list(tenant_id=tenant_id)
    return {"campaigns": [r.to_dict() for r in rows]}


@router.delete("/campaigns/{campaign_id}", summary="Supprimer une campagne")
async def delete_campaign(
    campaign_id: str, tenant_id: str = "local", session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    ok = await CampaignRepository(session).delete(campaign_id, tenant_id=tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign_not_found")
    await session.commit()
    return {"deleted": campaign_id}


@router.post(
    "/campaigns/{campaign_id}/send",
    summary="Envoyer une campagne — ciblage limité à l'audience consentante (Loi 29-2019)",
)
async def send_campaign(
    campaign_id: str,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    campaigns = CampaignRepository(session)
    camp = await campaigns.get(campaign_id, tenant_id=tenant_id)
    if camp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign_not_found")
    if camp.statut == "envoyee":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deja_envoyee")

    rows = await MarketingContactRepository(session).list(tenant_id=tenant_id)
    contacts = [_contact_of(r) for r in rows]
    # Gouvernance : seuls les contacts consentants pour la finalité sont ciblés.
    eligibles = filter_consented(contacts, camp.finalite)
    camp.nb_cibles = len(eligibles)
    camp.nb_envois = len(eligibles)
    camp.statut = "envoyee"
    camp.date_envoi = date.today()
    await session.flush()
    await session.commit()
    return {
        "campaign": camp.to_dict(),
        "exclus_non_consentants": len(contacts) - len(eligibles),
    }
