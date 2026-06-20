"""Segmentation déterministe (addendum §3.3, MKT-1).

Regroupe les contacts par **type × récence** (et expose des buckets RFM-like).
Aucun LLM : la segmentation est une règle reproductible.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from zolaos.agents.mkt.models import MarketingContact


def recency_bucket(contact: MarketingContact, as_of: date) -> str:
    """actif (≤30 j) | recent (≤90 j) | dormant (≤365 j) | inactif (>365 j ou jamais)."""
    if contact.derniere_interaction is None:
        return "inactif"
    j = (as_of - contact.derniere_interaction).days
    if j <= 30:
        return "actif"
    if j <= 90:
        return "recent"
    if j <= 365:
        return "dormant"
    return "inactif"


def segment_contacts(
    contacts: list[MarketingContact], *, as_of: date | None = None
) -> dict[str, list[MarketingContact]]:
    """Segmente par `<type>_<bucket récence>` (ex: 'client_actif', 'prospect_inactif')."""
    as_of = as_of or date.today()
    segments: dict[str, list[MarketingContact]] = defaultdict(list)
    for c in contacts:
        segments[f"{c.type}_{recency_bucket(c, as_of)}"].append(c)
    return dict(segments)


def segment_by_sector(contacts: list[MarketingContact]) -> dict[str, list[MarketingContact]]:
    """Segmente par secteur d'activité (secteur inconnu → 'non_renseigne')."""
    segments: dict[str, list[MarketingContact]] = defaultdict(list)
    for c in contacts:
        segments[c.secteur or "non_renseigne"].append(c)
    return dict(segments)
