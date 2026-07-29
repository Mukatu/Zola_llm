"""Cockpit de supervision (fleet) — vue d'ensemble des boxes clientes (Zolacortex).

Réservé au profil **cortex** et au rôle **admin**. Agrège, par tenant client, ce
qui est éparpillé ailleurs : connexion du tunnel (`REGISTRY`, en mémoire), état de
licence (`core.license_grants`), provisioning de box (`box_credential_prefix`) et
missions actives (`core.missions`). C'est la page « exploitation » qui manquait :
qui est en ligne, quelle licence, qui expire bientôt.

Lecture seule (aucune mutation) → pas de CSRF ; simple GET agrégé.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import require_admin
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.db.models import LicenseGrant, Mission, Tenant
from zolaos.db.session import get_session
from zolaos.tunnel.channel import REGISTRY

_log = get_logger("zolaos.api.v1.cortex_fleet")

router = APIRouter(
    prefix="/v1/cortex/fleet",
    tags=["cortex", "fleet"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)


def _license_status(grant: LicenseGrant | None, *, now: datetime) -> str:
    """Cycle de vie dérivé de la licence la plus récente (cf. cortex_entitlements)."""
    if grant is None:
        return "none"
    if grant.revoked_at is not None:
        return "revoked"
    if now >= grant.expires_at:
        return "expired"
    return "active"


class FleetRow(BaseModel):
    tenant_id: uuid.UUID
    name: str
    country: str
    is_active: bool
    box_provisioned: bool  # un credential de box a été émis
    box_connected: bool  # le tunnel de cette box est vivant (REGISTRY)
    license_status: str  # active | expired | revoked | none
    license_tier: str | None
    license_expires_at: datetime | None
    license_days_left: int | None  # jours avant expiration (si active)
    active_missions: int


class FleetSummary(BaseModel):
    clients: int
    boxes_connected: int
    licenses_active: int
    licenses_expiring_soon: int  # actives dont l'expiration est sous le seuil
    licenses_expired_or_revoked: int
    licenses_none: int


class FleetResponse(BaseModel):
    summary: FleetSummary
    rows: list[FleetRow]


@router.get("", response_model=FleetResponse, summary="Supervision des boxes clientes")
async def get_fleet(
    expiring_days: int = Query(default=30, ge=1, le=365, description="Seuil « expire bientôt »"),
    session: AsyncSession = Depends(get_session),
) -> FleetResponse:
    now = datetime.now(UTC)

    # 1. Tenants clients.
    clients = (
        (
            await session.execute(
                select(Tenant)
                .where(Tenant.tenant_type == "client")
                .order_by(Tenant.name)
                .limit(1000)
            )
        )
        .scalars()
        .all()
    )
    ids = [t.id for t in clients]
    if not ids:
        return FleetResponse(
            summary=FleetSummary(
                clients=0,
                boxes_connected=0,
                licenses_active=0,
                licenses_expiring_soon=0,
                licenses_expired_or_revoked=0,
                licenses_none=0,
            ),
            rows=[],
        )

    # 2. Licence la plus récente par tenant (DISTINCT ON — une requête, pas de N+1).
    grant_rows = (
        (
            await session.execute(
                select(LicenseGrant)
                .where(LicenseGrant.tenant_id.in_(ids))
                .order_by(LicenseGrant.tenant_id, LicenseGrant.created_at.desc())
                .distinct(LicenseGrant.tenant_id)
            )
        )
        .scalars()
        .all()
    )
    latest_grant: dict[uuid.UUID, LicenseGrant] = {g.tenant_id: g for g in grant_rows}

    # 3. Missions actives par tenant (agrégat groupé).
    mission_counts: dict[uuid.UUID, int] = dict(
        (
            await session.execute(
                select(Mission.client_tenant_id, func.count())
                .where(Mission.client_tenant_id.in_(ids), Mission.status == "active")
                .group_by(Mission.client_tenant_id)
            )
        ).all()
    )

    rows: list[FleetRow] = []
    connected = active = expiring = expired_revoked = none_cnt = 0
    for t in clients:
        grant = latest_grant.get(t.id)
        status = _license_status(grant, now=now)
        box_connected = str(t.id) in REGISTRY
        days_left: int | None = None
        if status == "active" and grant is not None:
            days_left = (grant.expires_at - now).days

        rows.append(
            FleetRow(
                tenant_id=t.id,
                name=t.name,
                country=t.country,
                is_active=t.is_active,
                box_provisioned=t.box_credential_prefix is not None,
                box_connected=box_connected,
                license_status=status,
                license_tier=grant.tier if grant is not None else None,
                license_expires_at=grant.expires_at if grant is not None else None,
                license_days_left=days_left,
                active_missions=mission_counts.get(t.id, 0),
            )
        )
        connected += box_connected
        if status == "active":
            active += 1
            if days_left is not None and days_left <= expiring_days:
                expiring += 1
        elif status in ("expired", "revoked"):
            expired_revoked += 1
        else:
            none_cnt += 1

    return FleetResponse(
        summary=FleetSummary(
            clients=len(clients),
            boxes_connected=connected,
            licenses_active=active,
            licenses_expiring_soon=expiring,
            licenses_expired_or_revoked=expired_revoked,
            licenses_none=none_cnt,
        ),
        rows=rows,
    )
