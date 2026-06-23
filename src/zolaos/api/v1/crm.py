"""Endpoints déterministes CRM (FE↔BE) — pipeline, scoring, relances.

Profil box. Calculs exacts sans LLM (pipeline_stats / score_lead / detect_relances).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from zolaos.agents.crm.engine import detect_relances, pipeline_stats, score_lead
from zolaos.agents.crm.models import Opportunity, Quote

router = APIRouter(prefix="/v1/crm", tags=["crm"])


class CrmRequest(BaseModel):
    opportunities: list[Opportunity] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)


@router.post("/analyze", summary="Pipeline + scoring de leads + relances (déterministe)")
def crm_analyze(req: CrmRequest) -> dict[str, Any]:
    stats = pipeline_stats(req.opportunities)
    scores = {o.id_externe: asdict(score_lead(o)) for o in req.opportunities}
    relances = [asdict(r) for r in detect_relances(req.quotes, req.opportunities)]
    return {"pipeline": asdict(stats), "scores": scores, "relances": relances}
