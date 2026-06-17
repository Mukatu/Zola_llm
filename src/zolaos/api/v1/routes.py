"""Routes /v1 — Phase 1 : /v1/query et /v1/agents."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from zolaos.agents.router import Pole, RouterError
from zolaos.api.auth import Principal, authenticate
from zolaos.api.dependencies import get_orchestrator
from zolaos.api.schemas import (
    AgentInfo,
    AgentResponseOut,
    AgentsListResponse,
    PlanOut,
    PlanStepOut,
    QueryRequest,
    QueryResponse,
    RoutingInfo,
)
from zolaos.core.orchestrator import Orchestrator

router = APIRouter(prefix="/v1", tags=["v1"])

# Catalogue déclaratif : permet d'exposer la roadmap aux clients API.
_AGENT_CATALOG: list[AgentInfo] = [
    AgentInfo(pole=Pole.GENERAL, label="Assistance générale", enabled=True, phase=1),
    AgentInfo(pole=Pole.HEALTH, label="Santé / Pharmacologie", enabled=False, phase=2),
    AgentInfo(pole=Pole.LEGAL, label="Droit OHADA + national CG", enabled=False, phase=2),
    AgentInfo(pole=Pole.ENGINEERING, label="Code Agent", enabled=False, phase=3),
    AgentInfo(pole=Pole.ERP, label="ERP (RH, finance, SYSCOHADA)", enabled=False, phase=4),
    AgentInfo(pole=Pole.GRC, label="Gouvernance / Risque / Conformité", enabled=False, phase=5),
    AgentInfo(pole=Pole.FINTECH, label="Fintech (KYC, scoring)", enabled=False, phase=6),
    AgentInfo(pole=Pole.CYBER, label="Cyber-défense", enabled=False, phase=7),
]


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),  # noqa: B008
    principal: Principal = Depends(authenticate),  # noqa: B008
) -> QueryResponse:
    """Point d'entrée unique pour adresser une requête utilisateur à ZolaOS."""
    _ = principal  # placeholder pour Phase 1 ; sera utilisé pour le tagging RBAC en Phase 2
    try:
        result = await orch.handle(payload.query)
    except RouterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"router_failed: {exc}",
        ) from exc

    return QueryResponse(
        request_id=result.request_id,
        decision=RoutingInfo(**result.decision.model_dump()),
        plan=(
            PlanOut(
                needs_planning=result.plan.needs_planning,
                rationale=result.plan.rationale,
                steps=[
                    PlanStepOut(**s.model_dump()) for s in result.plan.steps
                ],
            )
            if result.plan
            else None
        ),
        responses=[
            AgentResponseOut(
                pole=r.pole,
                content=r.content,
                model=r.model,
                duration_seconds=r.duration_seconds,
            )
            for r in result.responses
        ],
        duration_seconds=result.duration_seconds,
    )


@router.get("/agents", response_model=AgentsListResponse)
async def list_agents() -> AgentsListResponse:
    """Catalogue des pôles, avec leur état d'activation par phase."""
    return AgentsListResponse(
        agents=_AGENT_CATALOG,
        server_time=datetime.now(tz=timezone.utc),
    )
