"""Router `/v1/jurisdictions` — surface MOTEUR (packs pays), tous profils.

Expose :
- `GET /v1/jurisdictions` : catalogue déclaratif des packs (registre YAML,
  cf. `config/jurisdictions.yaml`) — public, sert à découvrir les pays
  branchables (« ajouter un pays = ajouter un pack », L1.4).
- `GET /v1/jurisdictions/current` : pack résolu pour l'appelant courant
  (sélection hybride : surcharge de requête > pays du principal > défaut,
  cf. `zolaos.core.jurisdictions.resolve_jurisdiction`).

Ce router NE PORTE PAS d'auth lui-même — `current_jurisdiction` dépend
d'`authenticate` en interne (il lui faut le principal pour la précédence
hybride), mais le router n'ajoute aucune dépendance supplémentaire au
montage : l'orchestrateur (`zolaos.api.main`) décide des dépendances
transverses (quota, CSRF box, etc.) selon le profil, comme pour les autres
routers de la surface moteur (`v1/routes.py`, `v1/openai_compat.py`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from zolaos.core.jurisdictions import JurisdictionPack, current_jurisdiction, load_packs

router = APIRouter(prefix="/v1/jurisdictions", tags=["jurisdictions"])


class JurisdictionsListResponse(BaseModel):
    """Catalogue des packs déclarés dans le registre."""

    packs: list[JurisdictionPack]


@router.get("", response_model=JurisdictionsListResponse)
async def list_jurisdictions() -> JurisdictionsListResponse:
    """Liste tous les packs juridiction déclarés (registre déclaratif)."""
    return JurisdictionsListResponse(packs=list(load_packs().values()))


@router.get("/current", response_model=JurisdictionPack)
async def current(
    pack: JurisdictionPack = Depends(current_jurisdiction),
) -> JurisdictionPack:
    """Pack résolu pour l'appelant courant (sélection hybride)."""
    return pack
