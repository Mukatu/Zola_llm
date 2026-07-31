"""Cockpit cabinet — GED : modèles de livrables & documents produits (Zolacortex).

Deux briques, un même router (profil **cortex**) :
- **Modèles** (`/templates`) : bibliothèque de squelettes de livrables, gérée par le
  rôle **admin**.
- **Livrables** (`/deliverables`) : documents produits pour une mission, instanciés
  d'un modèle (qui sème le squelette) ou vierges ; contenu markdown, statut
  draft→review→final, version incrémentée à chaque modification. Produits par tout
  consultant. Mutations sous CSRF.

La rédaction assistée par le corpus (le « + » IA) se branchera sur le contenu ;
ici on pose la bibliothèque + les documents versionnés.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.db.models import Deliverable, DeliverableTemplate, Mission
from zolaos.db.session import get_session
from zolaos.ged import build_skeleton

_log = get_logger("zolaos.api.v1.cortex_ged")

router = APIRouter(
    prefix="/v1/cortex/ged", tags=["cortex", "ged"], dependencies=[Depends(require_cortex)]
)

_DELIVERABLE_STATUSES = ("draft", "review", "final")


# ===========================================================================
# Modèles de livrables (bibliothèque) — mutations réservées admin
# ===========================================================================
class Section(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    guidance: str = Field(default="", max_length=1000)


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    offre: str | None
    description: str
    sections: list[dict[str, Any]]
    is_active: bool
    created_at: datetime


def _tpl_out(t: DeliverableTemplate) -> TemplateOut:
    return TemplateOut(
        id=t.id,
        name=t.name,
        offre=t.offre,
        description=t.description,
        sections=t.sections,
        is_active=t.is_active,
        created_at=t.created_at,
    )


class CreateTemplate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    offre: str | None = Field(default=None, max_length=64)
    description: str = Field(default="", max_length=2000)
    sections: list[Section] = Field(default_factory=list)


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: CreateTemplate,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> TemplateOut:
    tpl = DeliverableTemplate(
        name=payload.name,
        offre=payload.offre,
        description=payload.description,
        sections=[s.model_dump() for s in payload.sections],
        is_active=True,
        created_by_user_id=principal.user_id,
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    _log.info("ged.template.created", extra={"template_id": str(tpl.id)})
    return _tpl_out(tpl)


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    offre: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[TemplateOut]:
    stmt = select(DeliverableTemplate).order_by(DeliverableTemplate.name).limit(500)
    if offre is not None:
        stmt = stmt.where(DeliverableTemplate.offre == offre)
    if active_only:
        stmt = stmt.where(DeliverableTemplate.is_active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return [_tpl_out(t) for t in rows]


@router.get("/templates/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TemplateOut:
    tpl = await session.get(DeliverableTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    return _tpl_out(tpl)


class UpdateTemplate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    sections: list[Section] | None = None
    is_active: bool | None = None


@router.patch("/templates/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    payload: UpdateTemplate,
    _admin: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> TemplateOut:
    tpl = await session.get(DeliverableTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    if payload.name is not None:
        tpl.name = payload.name
    if payload.description is not None:
        tpl.description = payload.description
    if payload.sections is not None:
        tpl.sections = [s.model_dump() for s in payload.sections]
    if payload.is_active is not None:
        tpl.is_active = payload.is_active
    await session.commit()
    await session.refresh(tpl)
    return _tpl_out(tpl)


# ===========================================================================
# Livrables (documents par mission)
# ===========================================================================
class DeliverableBrief(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    template_id: uuid.UUID | None
    title: str
    status: str
    version: int
    updated_at: datetime


class DeliverableOut(DeliverableBrief):
    content: str


def _brief(d: Deliverable) -> DeliverableBrief:
    return DeliverableBrief(
        id=d.id,
        mission_id=d.mission_id,
        template_id=d.template_id,
        title=d.title,
        status=d.status,
        version=d.version,
        updated_at=d.updated_at,
    )


def _full(d: Deliverable) -> DeliverableOut:
    return DeliverableOut(**_brief(d).model_dump(), content=d.content)


class CreateDeliverable(BaseModel):
    mission_id: uuid.UUID
    template_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)


@router.post("/deliverables", response_model=DeliverableOut, status_code=status.HTTP_201_CREATED)
async def create_deliverable(
    payload: CreateDeliverable,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> DeliverableOut:
    """Crée un livrable pour une mission. Avec `template_id`, le contenu est **semé**
    du squelette du modèle (sections en markdown)."""
    if (await session.get(Mission, payload.mission_id)) is None:
        raise HTTPException(status_code=404, detail="mission_not_found")

    content = ""
    if payload.template_id is not None:
        tpl = await session.get(DeliverableTemplate, payload.template_id)
        if tpl is None:
            raise HTTPException(status_code=404, detail="template_not_found")
        content = build_skeleton(payload.title, tpl.sections)

    deliverable = Deliverable(
        mission_id=payload.mission_id,
        template_id=payload.template_id,
        title=payload.title,
        content=content,
        status="draft",
        version=1,
        created_by_user_id=principal.user_id,
    )
    session.add(deliverable)
    await session.commit()
    await session.refresh(deliverable)
    _log.info("ged.deliverable.created", extra={"deliverable_id": str(deliverable.id)})
    return _full(deliverable)


@router.get("/deliverables", response_model=list[DeliverableBrief])
async def list_deliverables(
    mission_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[DeliverableBrief]:
    stmt = select(Deliverable).order_by(Deliverable.updated_at.desc()).limit(limit)
    if mission_id is not None:
        stmt = stmt.where(Deliverable.mission_id == mission_id)
    if status_filter is not None:
        stmt = stmt.where(Deliverable.status == status_filter)
    rows = (await session.execute(stmt)).scalars().all()
    return [_brief(d) for d in rows]


@router.get("/deliverables/{deliverable_id}", response_model=DeliverableOut)
async def get_deliverable(
    deliverable_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DeliverableOut:
    d = await session.get(Deliverable, deliverable_id)
    if d is None:
        raise HTTPException(status_code=404, detail="deliverable_not_found")
    return _full(d)


class UpdateDeliverable(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    status: str | None = None


@router.patch("/deliverables/{deliverable_id}", response_model=DeliverableOut)
async def update_deliverable(
    deliverable_id: uuid.UUID,
    payload: UpdateDeliverable,
    _principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> DeliverableOut:
    """Met à jour un livrable. Toute modification du **contenu** incrémente la version."""
    d = await session.get(Deliverable, deliverable_id)
    if d is None:
        raise HTTPException(status_code=404, detail="deliverable_not_found")
    if payload.status is not None:
        if payload.status not in _DELIVERABLE_STATUSES:
            raise HTTPException(status_code=422, detail=f"invalid_status: {payload.status}")
        d.status = payload.status
    if payload.title is not None:
        d.title = payload.title
    if payload.content is not None and payload.content != d.content:
        d.content = payload.content
        d.version += 1
    await session.commit()
    await session.refresh(d)
    return _full(d)
