"""Routes /v1 — Phase 1 : /v1/query et /v1/agents."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import orjson
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from zolaos.agents.router import Pole, RouterError
from zolaos.api.auth import Principal, authenticate
from zolaos.api.dependencies import get_orchestrator
from zolaos.api.schemas import (
    AgentInfo,
    AgentResponseOut,
    AgentsListResponse,
    CitationOut,
    PlanOut,
    PlanStepOut,
    QueryRequest,
    QueryResponse,
    RoutingInfo,
)
from zolaos.core.logging import get_logger
from zolaos.core.orchestrator import Orchestrator

_log = get_logger("zolaos.api.v1.routes")

router = APIRouter(prefix="/v1", tags=["v1"])

# Catalogue déclaratif : permet d'exposer la roadmap aux clients API.
_AGENT_CATALOG: list[AgentInfo] = [
    AgentInfo(pole=Pole.GENERAL, label="Assistance générale", enabled=True, phase=1),
    AgentInfo(pole=Pole.HEALTH, label="Santé / Pharmacologie", enabled=False, phase=2),
    AgentInfo(pole=Pole.LEGAL, label="Droit OHADA + national CG", enabled=False, phase=2),
    AgentInfo(
        pole=Pole.ENGINEERING, label="Assistant code souverain (on-box)", enabled=True, phase=3
    ),
    AgentInfo(pole=Pole.ERP, label="ERP (RH, finance, SYSCOHADA)", enabled=False, phase=4),
    AgentInfo(pole=Pole.GRC, label="Gouvernance / Risque / Conformité", enabled=False, phase=5),
    AgentInfo(pole=Pole.FINTECH, label="Fintech (KYC, scoring)", enabled=False, phase=6),
    AgentInfo(pole=Pole.CYBER, label="Cyber-défense", enabled=False, phase=7),
]


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    principal: Principal = Depends(authenticate),
) -> QueryResponse:
    """Point d'entrée unique pour adresser une requête utilisateur à ZolaOS."""
    # Tenant dérivé de l'identité → l'agent fusionne le corpus privé du bon client.
    tenant_id = principal.tenant_id or "local"
    try:
        result = await orch.handle(payload.query, tenant_id=tenant_id, deep=payload.deep)
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
                steps=[PlanStepOut(**s.model_dump()) for s in result.plan.steps],
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
                grounding=r.grounding,
                citations=[
                    CitationOut(
                        index=c.index,
                        source_uri=c.source_uri,
                        source_id=c.source_id,
                        similarity=c.similarity,
                        schema_rag=r.rag_schema,
                        extrait=c.content,
                    )
                    for c in r.citations
                ],
            )
            for r in result.responses
        ],
        duration_seconds=result.duration_seconds,
    )


@router.post("/query/stream")
async def query_stream(
    payload: QueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    principal: Principal = Depends(authenticate),
) -> StreamingResponse:
    """Même chose que `/v1/query`, mais en SSE — la réponse s'affiche au fil de l'eau.

    Sans streaming l'utilisateur attend la génération complète (plusieurs secondes)
    devant un écran vide ; ici le premier token part dès que le routage est fait.
    Événements émis : `routing`, `plan`, `citations`, `token`, `done`, `error`.
    """
    tenant_id = principal.tenant_id or "local"

    async def events() -> AsyncIterator[bytes]:
        try:
            async for ev in orch.stream(payload.query, tenant_id=tenant_id, deep=payload.deep):
                yield b"data: " + orjson.dumps(ev) + b"\n\n"
        except RouterError as exc:
            yield b"data: " + orjson.dumps(
                {"type": "error", "detail": f"router_failed: {exc}"}
            ) + b"\n\n"
        except Exception as exc:  # le flux est déjà ouvert : on signale dans le flux
            _log.exception("query_stream.failed")
            yield b"data: " + orjson.dumps({"type": "error", "detail": str(exc)}) + b"\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # empêche un proxy de bufferiser et d'annuler le gain
            "Connection": "keep-alive",
        },
    )


@router.get("/agents", response_model=AgentsListResponse)
async def list_agents() -> AgentsListResponse:
    """Catalogue des pôles, avec leur état d'activation par phase."""
    return AgentsListResponse(
        agents=_AGENT_CATALOG,
        server_time=datetime.now(tz=UTC),
    )
