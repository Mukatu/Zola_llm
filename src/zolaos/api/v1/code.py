"""Assistant code souverain (produit client tech) — profil box.

Expose l'agent de codage ancré sur le dépôt DU CLIENT (`rag_code`, cloisonné par
tenant), servi par un modèle dédié code (Qwen2.5-Coder-32B) tournant LOCALEMENT
sur la box : le code du client ne quitte jamais ses murs. C'est la proposition de
valeur — là où une API externe (Claude Code, Copilot) est interdite pour raison
de souveraineté/IP.

Endpoints :
  - POST /v1/code/ask    : génération/refactor/debug/explication ancrée sur le dépôt.
  - GET  /v1/code/status : nb d'extraits indexés pour ce tenant (le dépôt est-il indexé ?).

Le corpus `rag_code` est peuplé hors-ligne par `scripts/index_codebase.py` (onboarding).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.engineering.code import CodeAgent, CodeArtifact
from zolaos.api.auth import current_tenant
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import RagCodeDocument
from zolaos.db.session import get_session
from zolaos.llm.factory import make_code_client

router = APIRouter(prefix="/v1/code", tags=["code"])

CodeIntent = Literal["generate", "refactor", "debug", "explain", "review", "test"]


class CodeAskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    intent: CodeIntent = "generate"
    language_hint: str | None = Field(default=None, max_length=32)
    structured_output: bool = False


class CodeAskResponse(BaseModel):
    intent: str
    content: str
    artifact: CodeArtifact | None = None
    repo_context: bool  # True si des extraits du dépôt indexé ont ancré la réponse
    model: str
    duration_seconds: float


@router.post(
    "/ask",
    response_model=CodeAskResponse,
    summary="Assistant code ancré sur le dépôt du client (souverain, on-box)",
)
async def code_ask(
    body: CodeAskRequest,
    tenant: str = Depends(current_tenant),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> CodeAskResponse:
    """Répond à une demande de code en s'ancrant sur le dépôt indexé du tenant.

    Le tenant est dérivé de l'identité authentifiée (jamais du client) → un tenant
    ne peut jamais requêter le code d'un autre (cloisonnement `rag_code`).
    """
    agent = CodeAgent(make_code_client(settings), settings, tenant_id=tenant)
    resp = await agent.answer(
        body.query,
        intent=body.intent,
        language_hint=body.language_hint,
        structured_output=body.structured_output,
        session=session,
    )
    return CodeAskResponse(
        intent=resp.intent,
        content=resp.content,
        artifact=resp.artifact,
        repo_context=resp.metadata.get("repo_context") == "yes",
        model=resp.metadata.get("model", settings.LLM_MODEL_CODE),
        duration_seconds=resp.duration_seconds,
    )


class CodeStatusResponse(BaseModel):
    tenant: str
    chunks_indexed: int
    indexed: bool


@router.get(
    "/status",
    response_model=CodeStatusResponse,
    summary="État de l'index du dépôt pour ce tenant",
)
async def code_status(
    tenant: str = Depends(current_tenant),
    session: AsyncSession = Depends(get_session),
) -> CodeStatusResponse:
    """Combien d'extraits de code sont indexés pour ce tenant (dépôt prêt ?)."""
    stmt = (
        select(func.count())
        .select_from(RagCodeDocument)
        .where(RagCodeDocument.tags.op("@>")([f"tenant:{tenant}"]))
    )
    n = int((await session.execute(stmt)).scalar_one())
    return CodeStatusResponse(tenant=tenant, chunks_indexed=n, indexed=n > 0)
