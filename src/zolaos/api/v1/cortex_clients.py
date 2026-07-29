"""Cockpit cabinet — annuaire des clients / tenants (Zolacortex).

Réservé au profil **cortex** et au rôle **admin**. Le modèle `Tenant` (cabinet |
client, `parent_tenant_id` rattachant un client à son cabinet) existait déjà mais
n'avait aucun endpoint : les clients étaient saisis en UUID à la main dans le
formulaire de mission. Ce router les rend gérables (créer / lister / rattacher),
et alimente le sélecteur de client des missions.

Sécurité : mutations sous CSRF ; validation stricte du `tenant_type`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.audit import record_audit
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.core.security import generate_box_credential
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import Mission, Tenant
from zolaos.db.session import get_session
from zolaos.tunnel.channel import disconnect_tenant

_log = get_logger("zolaos.api.v1.cortex_clients")

router = APIRouter(
    prefix="/v1/cortex/clients",
    tags=["cortex", "clients"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)

_TENANT_TYPES = ("cabinet", "client")


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    tenant_type: str
    parent_tenant_id: uuid.UUID | None
    country: str
    is_active: bool
    # Adresse de la Zolabox du client (RAG distant Zero Trust). NULL = pas de box.
    box_url: str | None
    # Prefix du credential de box (indique qu'une box est provisionnée). Le secret
    # complet n'est JAMAIS renvoyé ici — seulement à l'émission.
    box_credential_prefix: str | None
    created_at: datetime


def _to_out(t: Tenant) -> TenantOut:
    return TenantOut(
        id=t.id,
        name=t.name,
        tenant_type=t.tenant_type,
        parent_tenant_id=t.parent_tenant_id,
        country=t.country,
        is_active=t.is_active,
        box_url=t.box_url,
        box_credential_prefix=t.box_credential_prefix,
        created_at=t.created_at,
    )


@router.get("", response_model=list[TenantOut])
async def list_clients(
    tenant_type: str | None = Query(default=None, description="Filtre : cabinet | client"),
    session: AsyncSession = Depends(get_session),
) -> list[TenantOut]:
    stmt = select(Tenant).order_by(Tenant.created_at.desc()).limit(500)
    if tenant_type is not None:
        if tenant_type not in _TENANT_TYPES:
            raise HTTPException(status_code=422, detail=f"invalid_tenant_type: {tenant_type}")
        stmt = stmt.where(Tenant.tenant_type == tenant_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(t) for t in rows]


class CreateClientRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tenant_type: str = Field(default="client", description="client (défaut) | cabinet")
    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")
    # Rattachement d'un client à son cabinet onboardeur (facultatif).
    parent_tenant_id: uuid.UUID | None = None
    # Adresse de la Zolabox pour le RAG distant (renseignée au provisioning).
    box_url: str | None = Field(default=None, max_length=500)


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: CreateClientRequest,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> TenantOut:
    if payload.tenant_type not in _TENANT_TYPES:
        raise HTTPException(status_code=422, detail=f"invalid_tenant_type: {payload.tenant_type}")

    # Si un parent est fourni, il doit exister et être un cabinet.
    if payload.parent_tenant_id is not None:
        parent = await session.get(Tenant, payload.parent_tenant_id)
        if parent is None:
            raise HTTPException(status_code=422, detail="parent_not_found")
        if parent.tenant_type != "cabinet":
            raise HTTPException(status_code=422, detail="parent_not_a_cabinet")

    tenant = Tenant(
        name=payload.name,
        tenant_type=payload.tenant_type,
        parent_tenant_id=payload.parent_tenant_id,
        country=payload.country,
        is_active=True,
        box_url=payload.box_url,
    )
    session.add(tenant)
    await session.flush()  # matérialise tenant.id pour l'audit
    await record_audit(
        session,
        actor=principal,
        action="client.created",
        summary=f"Client « {tenant.name} » créé ({tenant.tenant_type})",
        target_type="tenant",
        target_id=tenant.id,
        extra={"name": tenant.name, "tenant_type": tenant.tenant_type, "country": tenant.country},
        request=request,
    )
    await session.commit()
    await session.refresh(tenant)
    _log.info(
        "cortex.client.created", extra={"tenant_id": str(tenant.id), "type": tenant.tenant_type}
    )
    return _to_out(tenant)


class MissionBrief(BaseModel):
    id: uuid.UUID
    offre: str
    status: str
    role: str  # "cabinet" | "client" — rôle de ce tenant dans la mission
    started_at: datetime
    expires_at: datetime | None


class ClientDetail(BaseModel):
    tenant: TenantOut
    missions: list[MissionBrief]


@router.get("/{tenant_id}", response_model=ClientDetail)
async def get_client(
    tenant_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ClientDetail:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")

    rows = (
        (
            await session.execute(
                select(Mission)
                .where(
                    or_(
                        Mission.client_tenant_id == tenant_id,
                        Mission.cabinet_tenant_id == tenant_id,
                    )
                )
                .order_by(Mission.started_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    missions = [
        MissionBrief(
            id=m.id,
            offre=m.offre,
            status=m.status,
            role="cabinet" if m.cabinet_tenant_id == tenant_id else "client",
            started_at=m.started_at,
            expires_at=m.expires_at,
        )
        for m in rows
    ]
    return ClientDetail(tenant=_to_out(tenant), missions=missions)


class UpdateClientRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
    parent_tenant_id: uuid.UUID | None = None
    box_url: str | None = Field(default=None, max_length=500)


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_client(
    tenant_id: uuid.UUID,
    payload: UpdateClientRequest,
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> TenantOut:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")

    if payload.parent_tenant_id is not None:
        parent = await session.get(Tenant, payload.parent_tenant_id)
        if parent is None or parent.tenant_type != "cabinet":
            raise HTTPException(status_code=422, detail="parent_not_a_cabinet")
        tenant.parent_tenant_id = payload.parent_tenant_id
    if payload.name is not None:
        tenant.name = payload.name
    if payload.is_active is not None:
        tenant.is_active = payload.is_active
    if payload.box_url is not None:
        tenant.box_url = payload.box_url

    await session.commit()
    await session.refresh(tenant)
    _log.info("cortex.client.updated", extra={"tenant_id": str(tenant.id)})
    return _to_out(tenant)


class BoxCredentialResponse(BaseModel):
    tenant_id: uuid.UUID
    # Secret complet — affiché UNE SEULE FOIS. À placer dans ZOLAOS_BOX_CREDENTIAL de la box.
    credential: str
    prefix: str


@router.post("/{tenant_id}/box-credential", response_model=BoxCredentialResponse)
async def issue_box_credential(
    tenant_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _csrf: None = Depends(require_csrf),
) -> BoxCredentialResponse:
    """(Ré)émet le credential de box du tenant. Rejouer invalide l'ancien (rotation)."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
    pepper = settings.API_KEY_PEPPER.get_secret_value()
    if not pepper:
        raise HTTPException(status_code=500, detail="api_key_pepper_not_configured")

    plain, prefix, cred_hash = generate_box_credential(pepper=pepper)
    tenant.box_credential_hash = cred_hash
    tenant.box_credential_prefix = prefix
    await record_audit(
        session,
        actor=principal,
        action="box_credential.issued",
        summary=f"Credential de box (ré)émis pour « {tenant.name} »",
        target_type="tenant",
        target_id=tenant.id,
        extra={"prefix": prefix},
        request=request,
    )
    await session.commit()
    _log.info("cortex.box_credential.issued", extra={"tenant_id": str(tenant.id), "prefix": prefix})
    return BoxCredentialResponse(tenant_id=tenant.id, credential=plain, prefix=prefix)


@router.delete("/{tenant_id}/box-credential", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_box_credential(
    tenant_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> Response:
    """Révoque le credential de box : la box ne pourra plus se déclarer au tunnel."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_not_found")
    tenant.box_credential_hash = None
    tenant.box_credential_prefix = None
    await record_audit(
        session,
        actor=principal,
        action="box_credential.revoked",
        summary=f"Credential de box révoqué pour « {tenant.name} »",
        target_type="tenant",
        target_id=tenant.id,
        request=request,
    )
    await session.commit()
    # Révocation immédiate : coupe aussi la connexion vivante éventuelle.
    await disconnect_tenant(str(tenant.id))
    _log.info("cortex.box_credential.revoked", extra={"tenant_id": str(tenant.id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
