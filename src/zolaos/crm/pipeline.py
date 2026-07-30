"""Pipeline commercial — calcul déterministe (synthèse pondérée, conversion).

Le pipeline **pondéré** = montant estimé × probabilité : la vue de prévision du
cabinet. Étapes ouvertes (lead/qualified/proposal) vs tranchées (won/lost). Tout en
entiers (XAF sans sous-unité).
"""

from __future__ import annotations

from typing import Any

STAGES: tuple[str, ...] = ("lead", "qualified", "proposal", "won", "lost")
OPEN_STAGES: tuple[str, ...] = ("lead", "qualified", "proposal")

# Probabilité indicative par étape (le commercial peut la surcharger à la main).
STAGE_PROBABILITY: dict[str, int] = {
    "lead": 10,
    "qualified": 30,
    "proposal": 60,
    "won": 100,
    "lost": 0,
}


def default_probability(stage: str) -> int:
    """Probabilité par défaut d'une étape (0 si étape inconnue)."""
    return STAGE_PROBABILITY.get(stage, 0)


def summarize_pipeline(
    opportunities: list[dict[str, Any]], *, currency: str = "XAF"
) -> dict[str, Any]:
    """Synthèse du pipeline : par étape (nombre/montant/pondéré) + agrégats.

    `opportunities` : dicts `{stage, amount_estimate, probability}`. Pondéré =
    montant × probabilité/100. `win_rate` = gagnées / (gagnées + perdues) en %
    (None si aucune affaire tranchée)."""
    by_stage: dict[str, dict[str, int]] = {
        s: {"count": 0, "amount": 0, "weighted": 0} for s in STAGES
    }
    won_count = lost_count = 0
    for o in opportunities:
        stage = o.get("stage")
        if stage not in by_stage:
            continue
        amount = int(o.get("amount_estimate", 0) or 0)
        prob = int(o.get("probability", 0) or 0)
        by_stage[stage]["count"] += 1
        by_stage[stage]["amount"] += amount
        by_stage[stage]["weighted"] += round(amount * prob / 100)
        if stage == "won":
            won_count += 1
        elif stage == "lost":
            lost_count += 1

    open_amount = sum(by_stage[s]["amount"] for s in OPEN_STAGES)
    open_weighted = sum(by_stage[s]["weighted"] for s in OPEN_STAGES)
    open_count = sum(by_stage[s]["count"] for s in OPEN_STAGES)
    decided = won_count + lost_count
    win_rate = round(won_count / decided * 100) if decided else None
    return {
        "by_stage": by_stage,
        "open_count": open_count,
        "open_amount": open_amount,
        "open_weighted": open_weighted,  # prévision pondérée du pipeline ouvert
        "won_amount": by_stage["won"]["amount"],
        "lost_amount": by_stage["lost"]["amount"],
        "win_rate": win_rate,
        "currency": currency,
    }
