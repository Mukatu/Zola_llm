"""Barème d'honoraires par grade (PSA).

**Mécanisme, pas de tarifs inventés** : le barème par défaut est à **zéro** (le PSA
mesure le temps ; honoraires/marge restent 0 tant que le cabinet n'a pas fixé ses
taux). Le cabinet renseigne `Settings.PSA_RATE_CARD_JSON` sans toucher au code.

Taux **horaires** en unités entières (XAF, sans sous-unité) : `bill_rate` = tarif
facturé au client, `cost_rate` = coût de production interne (base de la marge).
"""

from __future__ import annotations

import json
from typing import Any

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.psa.rates")

# Grades cabinet indicatifs (le barème peut en déclarer d'autres via la config).
GRADES: tuple[str, ...] = ("junior", "consultant", "senior", "manager", "partner")

_ZERO_RATE: dict[str, Any] = {"bill_rate": 0, "cost_rate": 0, "currency": "XAF"}


def _default_rate_card() -> dict[str, dict[str, Any]]:
    return {grade: dict(_ZERO_RATE) for grade in GRADES}


def load_rate_card(settings) -> dict[str, dict[str, Any]]:  # type: ignore[no-untyped-def]
    """Barème : défauts (zéro) surchargés par `PSA_RATE_CARD_JSON`.

    JSON invalide → journalisé, on retombe sur les défauts (ne casse jamais)."""
    card = _default_rate_card()
    raw = (getattr(settings, "PSA_RATE_CARD_JSON", "") or "").strip()
    if not raw:
        return card
    try:
        overrides = json.loads(raw)
    except ValueError as exc:
        _log.warning("psa.rate_card_json_invalid", error=str(exc))
        return card
    if not isinstance(overrides, dict):
        return card
    for grade, rate in overrides.items():
        if isinstance(rate, dict):
            card.setdefault(grade, dict(_ZERO_RATE)).update(rate)
    return card


def resolve_rates(grade: str | None, rate_card: dict[str, dict[str, Any]]) -> tuple[int, int]:
    """(bill_rate, cost_rate) horaires pour un grade. Grade absent/inconnu → (0, 0)."""
    rate = rate_card.get(grade or "", _ZERO_RATE)
    return int(rate.get("bill_rate", 0) or 0), int(rate.get("cost_rate", 0) or 0)
