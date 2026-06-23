"""Endpoint déterministe Marketing (FE↔BE) — segmentation + consentement.

Profil box. Privacy by design (Loi 29-2019) : l'audience éligible est calculée
**en code** (consentement + finalité) ; la génération de contenu passe par
l'agent via /v1/query, mais seulement sur une audience consentante.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zolaos.agents.mkt.consent import consent_summary
from zolaos.agents.mkt.models import MarketingContact
from zolaos.agents.mkt.segmentation import segment_contacts

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
