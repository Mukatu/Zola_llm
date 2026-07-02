"""Boucle de feedback des agents — capture du retour utilisateur (✓/✗ + correction).

Routeur TRANSVERSE (non lié à un pôle métier) : chaque réponse d'agent peut
recevoir un verdict ``up`` / ``down`` accompagné d'une correction experte et
d'un instantané du contexte RAG (citations/chunks).

C'est le socle de l'auto-amélioration : sans cette capture, le moteur ne peut
pas apprendre de l'usage réel.

Monté en dehors du bloc ``ZOLAOS_PROFILE == "box"`` car le feedback est
transverse (box + cortex).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.session import get_session
from zolaos.db.store_repo import AgentFeedbackRepository

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])

_VERDICTS_VALIDES = {"up", "down"}


# ---------------------------------------------------------------- schémas


class FeedbackIn(BaseModel):
    """Corps de la requête POST /v1/feedback."""

    agent: str = Field(..., description="Identifiant du pôle/module (ex : 'legal.ohada')")
    query: str = Field(..., description="Requête originale de l'utilisateur")
    response: str = Field(..., description="Réponse produite par l'agent")
    verdict: str = Field(..., description="Verdict de l'utilisateur : 'up' ou 'down'")
    request_id: str | None = Field(None, description="Identifiant de la requête originale")
    correction: str | None = Field(None, description="Correction experte (si verdict 'down')")
    context_snapshot: dict[str, Any] | None = Field(
        None, description="Instantané du contexte RAG (citations/chunks)"
    )

    @field_validator("verdict")
    @classmethod
    def _valider_verdict(cls, v: str) -> str:
        if v not in _VERDICTS_VALIDES:
            raise ValueError(f"verdict doit être 'up' ou 'down', reçu : {v!r}")
        return v


# ---------------------------------------------------------------- endpoints


@router.post("", status_code=status.HTTP_201_CREATED, summary="Enregistrer un feedback agent")
async def creer_feedback(
    body: FeedbackIn,
    tenant_id: str = "local",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Persiste le retour utilisateur sur une réponse d'agent."""
    repo = AgentFeedbackRepository(session)
    rec = await repo.create(
        {
            "tenant_id": tenant_id,
            "request_id": body.request_id,
            "agent": body.agent,
            "query": body.query,
            "response": body.response,
            "verdict": body.verdict,
            "correction": body.correction,
            "context_snapshot": body.context_snapshot,
        }
    )
    await session.commit()
    return rec.to_dict()


@router.get("", summary="Lister les feedbacks agents")
async def lister_feedbacks(
    tenant_id: str = "local",
    agent: str | None = None,
    verdict: str | None = None,
    request_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Liste les feedbacks, filtrable par agent, verdict ou request_id."""
    if verdict is not None and verdict not in _VERDICTS_VALIDES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"verdict invalide : doit être 'up' ou 'down', reçu : {verdict!r}",
        )
    repo = AgentFeedbackRepository(session)
    rows = await repo.list(tenant_id=tenant_id, agent=agent, verdict=verdict, request_id=request_id)
    return {"feedbacks": [r.to_dict() for r in rows], "total": len(rows)}


@router.get("/stats", summary="Statistiques up/down par agent")
async def stats_feedbacks(
    tenant_id: str = "local",
    agent: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retourne le décompte des verdicts (up/down) par agent."""
    repo = AgentFeedbackRepository(session)
    stats = await repo.count_by_verdict(tenant_id=tenant_id, agent=agent)
    return {"stats": stats}
