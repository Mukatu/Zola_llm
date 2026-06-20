"""Pôle Marketing (addendum BI/Commercial/Marketing)."""

from __future__ import annotations

from zolaos.agents.mkt.agent import MarketingAgent
from zolaos.agents.mkt.consent import (
    ConsentError,
    ConsentSummary,
    consent_summary,
    ensure_consent,
    filter_consented,
    is_eligible,
)
from zolaos.agents.mkt.models import Campaign, MarketingContact
from zolaos.agents.mkt.segmentation import recency_bucket, segment_by_sector, segment_contacts

__all__ = [
    "MarketingAgent",
    "MarketingContact",
    "Campaign",
    "segment_contacts",
    "segment_by_sector",
    "recency_bucket",
    "is_eligible",
    "filter_consented",
    "ensure_consent",
    "consent_summary",
    "ConsentSummary",
    "ConsentError",
]
