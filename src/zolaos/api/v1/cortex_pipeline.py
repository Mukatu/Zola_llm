"""Cockpit cabinet — CRM / pipeline commercial (Zolacortex).

L'amont du cabinet : prospect → opportunité → proposition → **gagné → mission**.
Réservé profil **cortex**. Un consultant gère SES opportunités ; les vues agrégées
(synthèse pondérée) et la **conversion en mission** sont réservées au rôle admin.
La conversion referme la boucle avec la production (temps) puis la facturation.

Mutations sous CSRF ; la conversion est **auditée** (`audit.log`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, authenticate, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.audit import record_audit
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.crm import STAGES, default_probability, summarize_pipeline
from zolaos.db.models import Mission, Opportunity, Tenant
from zolaos.db.session import get_session

_log = get_logger("zolaos.api.v1.cortex_pipeline")

router = APIRouter(
    prefix="/v1/cortex/pipeline", tags=["cortex", "crm"], dependencies=[Depends(require_cortex)]
)


class OpportunityOut(BaseModel):
    id: uuid.UUID
    title: str
    client_tenant_id: uuid.UUID | None
    client_name: str | None
    offre: str
    amount_estimate: int
    currency: str
    stage: str
    probability: int
    weighted: int  # amount_estimate * probability / 100 (prévision pondérée)
    expected_close_date: date | None
    owner_user_id: uuid.UUID | None
    mission_id: uuid.UUID | None
    notes: str
    created_at: datetime


def _to_out(o: Opportunity) -> OpportunityOut:
    return OpportunityOut(
        id=o.id,
        title=o.title,
        client_tenant_id=o.client_tenant_id,
        client_name=o.client_name,
        offre=o.offre,
        amount_estimate=o.amount_estimate,
        currency=o.currency,
        stage=o.stage,
        probability=o.probability,
        weighted=round(o.amount_estimate * o.probability / 100),
        expected_close_date=o.expected_close_date,
        owner_user_id=o.owner_user_id,
        mission_id=o.mission_id,
        notes=o.notes,
        created_at=o.created_at,
    )


# ---------------------------------------------------------------------------
# Création
# ---------------------------------------------------------------------------
class CreateOpportunity(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    offre: str = Field(min_length=1, max_length=64)
    amount_estimate: int = Field(default=0, ge=0)
    client_tenant_id: uuid.UUID | None = None
    client_name: str | None = Field(default=None, max_length=200)
    expected_close_date: date | None = None
    notes: str = Field(default="", max_length=1000)


@router.post("", response_model=OpportunityOut, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    payload: CreateOpportunity,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> OpportunityOut:
    """Crée une opportunité (étape `lead`) détenue par le consultant courant."""
    if payload.client_tenant_id is None and not (payload.client_name or "").strip():
        raise HTTPException(status_code=422, detail="need_client_tenant_or_name")
    opp = Opportunity(
        title=payload.title,
        offre=payload.offre,
        amount_estimate=payload.amount_estimate,
        client_tenant_id=payload.client_tenant_id,
        client_name=payload.client_name,
        expected_close_date=payload.expected_close_date,
        notes=payload.notes,
        stage="lead",
        probability=default_probability("lead"),
        owner_user_id=principal.user_id,
    )
    session.add(opp)
    await session.commit()
    await session.refresh(opp)
    _log.info("crm.opportunity.created", extra={"opportunity_id": str(opp.id)})
    return _to_out(opp)


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------
@router.get("", response_model=list[OpportunityOut])
async def list_opportunities(
    stage: str | None = Query(default=None),
    mine: bool = Query(default=False, description="Limiter à mes opportunités"),
    limit: int = Query(default=200, ge=1, le=1000),
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
) -> list[OpportunityOut]:
    stmt = select(Opportunity).order_by(Opportunity.created_at.desc()).limit(limit)
    if mine:
        stmt = stmt.where(Opportunity.owner_user_id == principal.user_id)
    if stage is not None:
        stmt = stmt.where(Opportunity.stage == stage)
    rows = (await session.execute(stmt)).scalars().all()
    return [_to_out(o) for o in rows]


# ---------------------------------------------------------------------------
# Synthèse (pondérée) — admin — AVANT /{opportunity_id}
# ---------------------------------------------------------------------------
@router.get("/summary", summary="Synthèse du pipeline (pondérée)")
async def pipeline_summary(
    _admin: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    rows = (await session.execute(select(Opportunity))).scalars().all()
    opps = [
        {"stage": o.stage, "amount_estimate": o.amount_estimate, "probability": o.probability}
        for o in rows
    ]
    return summarize_pipeline(opps)


# ---------------------------------------------------------------------------
# Édition + mouvement d'étape
# ---------------------------------------------------------------------------
async def _get_or_404(session: AsyncSession, opportunity_id: uuid.UUID) -> Opportunity:
    opp = await session.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="opportunity_not_found")
    return opp


class UpdateOpportunity(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    amount_estimate: int | None = Field(default=None, ge=0)
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    client_tenant_id: uuid.UUID | None = None
    stage: str | None = None


@router.patch("/{opportunity_id}", response_model=OpportunityOut)
async def update_opportunity(
    opportunity_id: uuid.UUID,
    payload: UpdateOpportunity,
    principal: Principal = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> OpportunityOut:
    """Édite / fait avancer une opportunité (propriétaire ou admin). Changer d'étape
    sans fixer la probabilité applique la valeur par défaut de l'étape."""
    opp = await _get_or_404(session, opportunity_id)
    if opp.owner_user_id != principal.user_id and "admin:users" not in principal.scopes:
        raise HTTPException(status_code=403, detail="not_owner")

    if payload.stage is not None:
        if payload.stage not in STAGES:
            raise HTTPException(status_code=422, detail=f"invalid_stage: {payload.stage}")
        if payload.stage != opp.stage:
            opp.stage = payload.stage
            if payload.probability is None:
                opp.probability = default_probability(payload.stage)
    if payload.probability is not None:
        opp.probability = payload.probability
    if payload.title is not None:
        opp.title = payload.title
    if payload.amount_estimate is not None:
        opp.amount_estimate = payload.amount_estimate
    if payload.expected_close_date is not None:
        opp.expected_close_date = payload.expected_close_date
    if payload.notes is not None:
        opp.notes = payload.notes
    if payload.client_tenant_id is not None:
        opp.client_tenant_id = payload.client_tenant_id

    await session.commit()
    await session.refresh(opp)
    return _to_out(opp)


# ---------------------------------------------------------------------------
# Conversion en mission (opportunité gagnée → production) — admin
# ---------------------------------------------------------------------------
class ConvertOpportunity(BaseModel):
    ttl_hours: float = Field(default=720.0, gt=0)  # 30 j par défaut


class ConvertResponse(BaseModel):
    opportunity: OpportunityOut
    mission_id: uuid.UUID


@router.post("/{opportunity_id}/convert", response_model=ConvertResponse)
async def convert_opportunity(
    opportunity_id: uuid.UUID,
    payload: ConvertOpportunity,
    request: Request,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> ConvertResponse:
    """Convertit une opportunité **gagnée** en `Mission` (référme la boucle vers la
    production). Exige un client tenant réel et un cabinet pour le consultant."""
    opp = await _get_or_404(session, opportunity_id)
    if opp.stage != "won":
        raise HTTPException(status_code=409, detail="must_be_won")
    if opp.mission_id is not None:
        raise HTTPException(status_code=409, detail="already_converted")
    if opp.client_tenant_id is None:
        raise HTTPException(status_code=422, detail="need_client_tenant")

    if principal.tenant_uuid is None:
        raise HTTPException(status_code=403, detail="principal_has_no_tenant")
    cabinet = await session.get(Tenant, principal.tenant_uuid)
    if cabinet is None or cabinet.tenant_type != "cabinet":
        raise HTTPException(status_code=403, detail="principal_must_be_cabinet")
    client = await session.get(Tenant, opp.client_tenant_id)
    if client is None or client.tenant_type != "client":
        raise HTTPException(status_code=422, detail="client_tenant_invalid")

    now = datetime.now(UTC)
    mission = Mission(
        cabinet_tenant_id=cabinet.id,
        client_tenant_id=opp.client_tenant_id,
        offre=opp.offre,
        consultant_user_id=opp.owner_user_id or principal.user_id,
        expires_at=now + timedelta(hours=payload.ttl_hours),
        status="active",
        scope_tags=[],
    )
    session.add(mission)
    await session.flush()
    opp.mission_id = mission.id
    await record_audit(
        session,
        actor=principal,
        action="opportunity.converted",
        summary=f"Opportunité « {opp.title} » convertie en mission ({opp.offre})",
        target_type="tenant",
        target_id=opp.client_tenant_id,
        extra={"opportunity_id": str(opp.id), "mission_id": str(mission.id), "offre": opp.offre},
        request=request,
    )
    await session.commit()
    await session.refresh(opp)
    _log.info(
        "crm.opportunity.converted",
        extra={"opportunity_id": str(opp.id), "mission_id": str(mission.id)},
    )
    return ConvertResponse(opportunity=_to_out(opp), mission_id=mission.id)
