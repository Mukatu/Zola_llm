"""Moteur de tarification — usage → coût, par tier.

On fournit le **mécanisme** ; les **prix** sont une décision commerciale, JAMAIS
inventés ici. Le barème par défaut est à **zéro** (la vue montre l'usage réel, coût
0 tant que le barème n'est pas défini). L'exploitant fixe ses tarifs via
`Settings.BILLING_PRICING_JSON` sans toucher au code.

Modèle : par tier, un **forfait mensuel** (`monthly_base`) incluant un quota de
requêtes (`included_requests`) ; au-delà, un **dépassement** facturé par tranche de
1000 requêtes (`overage_per_1k`). Devise indicative `currency` (défaut XAF, CEMAC).
"""

from __future__ import annotations

import json
import math
from typing import Any

from zolaos.core.logging import get_logger
from zolaos.licensing import TIERS

_log = get_logger("zolaos.billing.pricing")

# Structure d'un tarif de tier. Valeurs à zéro = « à définir » (aucun prix inventé).
_ZERO_PRICE: dict[str, Any] = {
    "monthly_base": 0,
    "included_requests": 0,
    "overage_per_1k": 0,
    "currency": "XAF",
}


def _default_pricing() -> dict[str, dict[str, Any]]:
    """Barème par défaut : chaque tier connu à zéro (mécanisme sans prix)."""
    return {tier: dict(_ZERO_PRICE) for tier in TIERS}


def load_pricing(settings) -> dict[str, dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Charge le barème : défauts (zéro) surchargés par `BILLING_PRICING_JSON`.

    Un JSON invalide ne casse rien : on journalise et on retombe sur les défauts."""
    pricing = _default_pricing()
    raw = getattr(settings, "BILLING_PRICING_JSON", "") or ""
    raw = raw.strip()
    if not raw:
        return pricing
    try:
        overrides = json.loads(raw)
    except ValueError as exc:
        _log.warning("billing.pricing_json_invalid", error=str(exc))
        return pricing
    if not isinstance(overrides, dict):
        return pricing
    for tier, price in overrides.items():
        if isinstance(price, dict):
            pricing.setdefault(tier, dict(_ZERO_PRICE)).update(price)
    return pricing


def compute_bill(
    tier: str | None,
    *,
    requests: int,
    tokens: int,
    pricing: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Calcule le coût d'un usage pour un tier donné selon le barème.

    Tier inconnu / sans barème → forfait 0 et dépassement 0 (mais l'usage reste
    affiché). Le calcul est déterministe (le moteur calcule, jamais d'à-peu-près)."""
    price = pricing.get(tier or "", _ZERO_PRICE)
    base = int(price.get("monthly_base", 0) or 0)
    included = int(price.get("included_requests", 0) or 0)
    per_1k = int(price.get("overage_per_1k", 0) or 0)
    currency = price.get("currency", "XAF")

    overage_requests = max(0, requests - included)
    overage_cost = math.ceil(overage_requests / 1000) * per_1k
    total = base + overage_cost
    return {
        "monthly_base": base,
        "included_requests": included,
        "overage_requests": overage_requests,
        "overage_per_1k": per_1k,
        "overage_cost": overage_cost,
        "total": total,
        "currency": currency,
    }
