"""Cockpit cabinet — gestion des entitlements de modules (Zolacortex).

Réservé au profil **cortex** et au rôle **admin**. C'est le pendant *cabinet* de
l'entitlement vérifié côté box (`zolaos.licensing`) : ici Polaris **émet** (signe),
**liste**, **révoque** et **(re)livre** les licences de modules par tenant client.

Doctrine de sécurité (rappel) : le grant est signé en **RS256 asymétrique** avec la
clé PRIVÉE de Polaris (`ENTITLEMENT_PRIVATE_KEY`, jamais sur une box). La box n'a
que la clé PUBLIQUE → elle vérifie, ne forge pas. Ce cockpit est le SEUL endroit
qui détient la clé privée ; il exige donc profil cortex + rôle admin + CSRF.

Modèle **hybride** : un `tier` (bundle) + des `modules` optionnels à la carte.
Modèles effectifs = tier ∪ options, recalculés à la lecture. À l'émission d'une
nouvelle licence pour un tenant, les précédentes actives sont **révoquées** : une
seule licence vivante par tenant (« renouvellement remplace »).

Livraison : le jeton signé se dépose sur la box, soit en fichier
(`ENTITLEMENT_LICENSE_FILE`) soit inline (`ENTITLEMENT_LICENSE_JWT`). L'endpoint
`GET …/tenant/{id}/active` renvoie le jeton vivant — socle du refresh par tunnel.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import LicenseGrant, Tenant
from zolaos.db.session import get_session
from zolaos.licensing import (
    MODULES,
    TIERS,
    Entitlement,
    effective_modules_for,
    sign_entitlement,
)

_log = get_logger("zolaos.api.v1.cortex_entitlements")

router = APIRouter(
    prefix="/v1/cortex/entitlements",
    tags=["cortex", "entitlements"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)

_MAX_DAYS = 3660  # ~10 ans : garde-fou contre une licence quasi-perpétuelle par typo


def _status(grant: LicenseGrant, *, now: datetime) -> str:
    """Cycle de vie dérivé : revoked > expired > active (jamais dénormalisé)."""
    if grant.revoked_at is not None:
        return "revoked"
    if now >= grant.expires_at:
        return "expired"
    return "active"


# ---------------------------------------------------------------------------
# Schémas de sortie
# ---------------------------------------------------------------------------
class GrantOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    license_id: str
    tier: str
    modules: list[str]  # options à la carte (EN PLUS du tier)
    effective_modules: list[str]  # tier ∪ options, borné au catalogue
    status: str  # active | expired | revoked
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class GrantWithToken(GrantOut):
    """Vue avec le jeton signé (livrable) — renvoyée à l'émission, au détail et à
    la livraison. Réservée cortex + admin (le cockpit détient déjà la clé privée)."""

    token: str


def _to_out(g: LicenseGrant, *, now: datetime) -> GrantOut:
    return GrantOut(
        id=g.id,
        tenant_id=g.tenant_id,
        license_id=g.license_id,
        tier=g.tier,
        modules=list(g.modules),
        effective_modules=sorted(effective_modules_for(g.tier, g.modules)),
        status=_status(g, now=now),
        issued_at=g.issued_at,
        expires_at=g.expires_at,
        revoked_at=g.revoked_at,
        created_at=g.created_at,
    )


def _to_out_with_token(g: LicenseGrant, *, now: datetime) -> GrantWithToken:
    base = _to_out(g, now=now)
    return GrantWithToken(**base.model_dump(), token=g.token)


# ---------------------------------------------------------------------------
# Catalogue (alimente le formulaire du cockpit)
# ---------------------------------------------------------------------------
class CatalogueOut(BaseModel):
    tiers: dict[str, list[str]]  # tier → modules de base
    modules: list[str]  # catalogue complet (unités vendables)


@router.get("/catalogue", response_model=CatalogueOut)
async def get_catalogue() -> CatalogueOut:
    """Tiers et modules vendables — pour peupler le formulaire d'émission côté UI."""
    return CatalogueOut(
        tiers={name: sorted(mods) for name, mods in TIERS.items()},
        modules=sorted(MODULES),
    )


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------
@router.get("", response_model=list[GrantOut])
async def list_grants(
    tenant_id: uuid.UUID | None = Query(default=None, description="Filtre par tenant"),
    active_only: bool = Query(default=False, description="Uniquement les licences vivantes"),
    session: AsyncSession = Depends(get_session),
) -> list[GrantOut]:
    now = datetime.now(UTC)
    stmt = select(LicenseGrant).order_by(LicenseGrant.created_at.desc()).limit(500)
    if tenant_id is not None:
        stmt = stmt.where(LicenseGrant.tenant_id == tenant_id)
    rows = (await session.execute(stmt)).scalars().all()
    out = [_to_out(g, now=now) for g in rows]
    if active_only:
        out = [g for g in out if g.status == "active"]
    return out


# ---------------------------------------------------------------------------
# Émission (signe + persiste + supersede)
# ---------------------------------------------------------------------------
class IssueRequest(BaseModel):
    tenant_id: uuid.UUID
    tier: str = Field(description=f"Bundle de base : {' | '.join(sorted(TIERS))}")
    modules: list[str] = Field(
        default_factory=list, description="Options à la carte EN PLUS du tier"
    )
    days: int = Field(gt=0, le=_MAX_DAYS, description="Durée de validité (jours)")
    license_id: str | None = Field(
        default=None, max_length=64, description="Identifiant de licence (défaut : uuid4)"
    )


@router.post("", response_model=GrantWithToken, status_code=status.HTTP_201_CREATED)
async def issue_grant(
    payload: IssueRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> GrantWithToken:
    """Émet (signe) une licence de modules pour un tenant client, la persiste, et
    **révoque les licences actives précédentes** de ce tenant (renouvellement)."""
    # 1. Validation métier stricte (jamais faire confiance au formulaire).
    if payload.tier not in TIERS:
        raise HTTPException(status_code=422, detail=f"invalid_tier: {payload.tier}")
    unknown = sorted(set(payload.modules) - MODULES)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown_modules: {unknown}")

    tenant = await session.get(Tenant, payload.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant_not_found")
    if tenant.tenant_type != "client":
        # Une licence de modules s'applique à une box = un tenant client.
        raise HTTPException(status_code=422, detail="tenant_must_be_client")

    # 2. Clé privée d'émission — présente uniquement côté cortex. Absente → refus net.
    private_key = settings.ENTITLEMENT_PRIVATE_KEY.get_secret_value()
    if not private_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="signing_key_not_configured",
        )

    license_id = payload.license_id or str(uuid.uuid4())
    exists = (
        await session.execute(select(LicenseGrant.id).where(LicenseGrant.license_id == license_id))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="license_id_already_exists"
        )

    # 3. Construit l'entitlement et le SIGNE (RS256, clé privée). Options normalisées
    #    (dédoublonnées, triées) pour un jeton déterministe.
    now = datetime.now(UTC)
    options = sorted(set(payload.modules))
    entitlement = Entitlement(
        tenant_id=str(payload.tenant_id),
        tier=payload.tier,
        modules=options,
        license_id=license_id,
        issued_at=now,
        expires_at=now + timedelta(days=payload.days),
    )
    token = sign_entitlement(entitlement, private_key_pem=private_key)

    # 4. Renouvellement : révoque les licences vivantes précédentes du tenant.
    prior = (
        (
            await session.execute(
                select(LicenseGrant).where(
                    LicenseGrant.tenant_id == payload.tenant_id,
                    LicenseGrant.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for old in prior:
        old.revoked_at = now

    # 5. Persiste la nouvelle licence.
    grant = LicenseGrant(
        tenant_id=payload.tenant_id,
        license_id=license_id,
        tier=payload.tier,
        modules=options,
        token=token,
        issued_at=entitlement.issued_at,
        expires_at=entitlement.expires_at,
        issued_by_user_id=principal.user_id,
    )
    session.add(grant)
    await session.commit()
    await session.refresh(grant)
    _log.info(
        "cortex.entitlement.issued",
        extra={
            "tenant_id": str(payload.tenant_id),
            "license_id": license_id,
            "tier": payload.tier,
            "superseded": len(prior),
        },
    )
    return _to_out_with_token(grant, now=now)


# ---------------------------------------------------------------------------
# Détail (avec jeton, pour re-livraison)
# ---------------------------------------------------------------------------
async def _get_or_404(session: AsyncSession, grant_id: uuid.UUID) -> LicenseGrant:
    grant = await session.get(LicenseGrant, grant_id)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grant_not_found")
    return grant


@router.get("/{grant_id}", response_model=GrantWithToken)
async def get_grant(
    grant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> GrantWithToken:
    grant = await _get_or_404(session, grant_id)
    return _to_out_with_token(grant, now=datetime.now(UTC))


# ---------------------------------------------------------------------------
# Livraison : la licence VIVANTE d'un tenant (socle du refresh par tunnel)
# ---------------------------------------------------------------------------
@router.get("/tenant/{tenant_id}/active", response_model=GrantWithToken)
async def get_active_for_tenant(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> GrantWithToken:
    """Licence **active** (non révoquée, non expirée) d'un tenant + son jeton.

    C'est le point de livraison : l'exploitant y copie le jeton pour le déposer sur
    la box, et le futur job de refresh par tunnel le tirera d'ici. 404 si aucune."""
    now = datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(LicenseGrant)
                .where(
                    LicenseGrant.tenant_id == tenant_id,
                    LicenseGrant.revoked_at.is_(None),
                    LicenseGrant.expires_at > now,
                )
                .order_by(LicenseGrant.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_active_license")
    return _to_out_with_token(rows[0], now=now)


# ---------------------------------------------------------------------------
# Révocation
# ---------------------------------------------------------------------------
@router.post("/{grant_id}/revoke", response_model=GrantOut)
async def revoke_grant(
    grant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> GrantOut:
    """Révoque une licence (immédiat, irréversible). La box perd l'accès dès qu'elle
    recharge/re-vérifie ; le prochain refresh tunnel ne la re-livrera plus."""
    now = datetime.now(UTC)
    grant = await _get_or_404(session, grant_id)
    if grant.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_revoked")
    grant.revoked_at = now
    await session.commit()
    await session.refresh(grant)
    _log.info(
        "cortex.entitlement.revoked",
        extra={"grant_id": str(grant.id), "tenant_id": str(grant.tenant_id)},
    )
    return _to_out(grant, now=now)
