"""Pôle Commercial / CRM & Ventes (addendum BI/Commercial/Marketing)."""

from __future__ import annotations

from zolaos.agents.crm.engine import (
    LeadScore,
    LeadScoringWeights,
    PipelineStats,
    RelanceItem,
    detect_relances,
    pipeline_stats,
    quote_to_invoice,
    score_lead,
)
from zolaos.agents.crm.models import Customer, Opportunity, Quote, QuoteLine

__all__ = [
    "Customer",
    "Opportunity",
    "Quote",
    "QuoteLine",
    "PipelineStats",
    "pipeline_stats",
    "LeadScore",
    "LeadScoringWeights",
    "score_lead",
    "RelanceItem",
    "detect_relances",
    "quote_to_invoice",
]
