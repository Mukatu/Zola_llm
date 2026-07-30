"""Tests unitaires zolaos.crm.pipeline (synthèse pondérée du pipeline commercial).

Couvre :
- default_probability : probabilité indicative par étape (0 si étape inconnue)
- summarize_pipeline : agrégats par étape, pipeline ouvert pondéré, taux de
  transformation (win_rate), et le cas d'un pipeline vide
"""

from __future__ import annotations

from zolaos.crm.pipeline import default_probability, summarize_pipeline


def test_default_probability_known_stages() -> None:
    assert default_probability("lead") == 10
    assert default_probability("qualified") == 30
    assert default_probability("proposal") == 60
    assert default_probability("won") == 100
    assert default_probability("lost") == 0


def test_default_probability_unknown_stage() -> None:
    assert default_probability("bogus") == 0


def test_summarize_pipeline_mixed_stages() -> None:
    opportunities = [
        {"stage": "qualified", "amount_estimate": 1_000_000, "probability": 30},
        {"stage": "proposal", "amount_estimate": 2_000_000, "probability": 60},
        {"stage": "won", "amount_estimate": 500_000, "probability": 100},
        {"stage": "lost", "amount_estimate": 800_000, "probability": 0},
    ]
    summary = summarize_pipeline(opportunities)

    assert summary["open_amount"] == 3_000_000
    assert summary["open_weighted"] == 1_500_000  # 300000 + 1200000
    assert summary["won_amount"] == 500_000
    assert summary["lost_amount"] == 800_000
    assert summary["win_rate"] == 50
    assert summary["currency"] == "XAF"

    assert summary["by_stage"]["qualified"] == {
        "count": 1,
        "amount": 1_000_000,
        "weighted": 300_000,
    }
    assert summary["by_stage"]["proposal"] == {
        "count": 1,
        "amount": 2_000_000,
        "weighted": 1_200_000,
    }
    assert summary["by_stage"]["won"] == {"count": 1, "amount": 500_000, "weighted": 500_000}
    assert summary["by_stage"]["lost"] == {"count": 1, "amount": 800_000, "weighted": 0}
    assert summary["by_stage"]["lead"] == {"count": 0, "amount": 0, "weighted": 0}
    assert summary["open_count"] == 2


def test_summarize_pipeline_empty() -> None:
    summary = summarize_pipeline([])

    assert summary["open_count"] == 0
    assert summary["open_amount"] == 0
    assert summary["open_weighted"] == 0
    assert summary["won_amount"] == 0
    assert summary["lost_amount"] == 0
    assert summary["win_rate"] is None
    assert summary["currency"] == "XAF"
