"""Tests unitaires PSA — barème (zolaos.psa.rates) et économie (zolaos.psa.economics).

Aucun HTTP, aucune DB : calcul déterministe pur.
"""

from __future__ import annotations

from types import SimpleNamespace

from zolaos.psa.economics import (
    compute_engagement_economics,
    compute_utilization,
    entry_amounts,
)
from zolaos.psa.rates import load_rate_card, resolve_rates

# ----------------------------------------------------------------------------
# rates.py
# ----------------------------------------------------------------------------


def test_resolve_rates_known_grade():
    rate_card = {"senior": {"bill_rate": 45000, "cost_rate": 18000}}
    assert resolve_rates("senior", rate_card) == (45000, 18000)


def test_resolve_rates_unknown_or_none_grade_is_zero():
    rate_card = {"senior": {"bill_rate": 45000, "cost_rate": 18000}}
    assert resolve_rates("stagiaire", rate_card) == (0, 0)
    assert resolve_rates(None, rate_card) == (0, 0)


def test_load_rate_card_empty_json_gives_zeros():
    settings = SimpleNamespace(PSA_RATE_CARD_JSON="")
    card = load_rate_card(settings)
    assert card["senior"]["bill_rate"] == 0
    assert card["senior"]["cost_rate"] == 0


def test_load_rate_card_invalid_json_falls_back_to_zeros_without_raising():
    settings = SimpleNamespace(PSA_RATE_CARD_JSON="{not-valid-json")
    card = load_rate_card(settings)
    assert card["junior"]["bill_rate"] == 0
    assert card["junior"]["cost_rate"] == 0


def test_load_rate_card_applies_overrides():
    settings = SimpleNamespace(
        PSA_RATE_CARD_JSON='{"senior":{"bill_rate":45000,"cost_rate":18000}}'
    )
    card = load_rate_card(settings)
    assert card["senior"]["bill_rate"] == 45000
    assert card["senior"]["cost_rate"] == 18000
    # Les autres grades restent à zéro (défauts non touchés par l'override).
    assert card["junior"]["bill_rate"] == 0


# ----------------------------------------------------------------------------
# economics.py — entry_amounts
# ----------------------------------------------------------------------------


def test_entry_amounts_billable():
    amt = entry_amounts(minutes=480, bill_rate=45000, cost_rate=18000, billable=True)
    assert amt["honoraires"] == 360000
    assert amt["cost"] == 144000


def test_entry_amounts_non_billable_has_zero_honoraires_but_cost_computed():
    amt = entry_amounts(minutes=480, bill_rate=45000, cost_rate=18000, billable=False)
    assert amt["honoraires"] == 0
    assert amt["cost"] == 144000


# ----------------------------------------------------------------------------
# economics.py — compute_engagement_economics
# ----------------------------------------------------------------------------


def test_compute_engagement_economics_mix_and_rejected_excluded():
    entries = [
        # approuvée, facturable : 480 min @ 45000/18000
        {
            "minutes": 480,
            "bill_rate": 45000,
            "cost_rate": 18000,
            "billable": True,
            "status": "approved",
        },
        # soumise, non facturable : 120 min @ 45000/18000 (honoraires nuls, coût compté)
        {
            "minutes": 120,
            "bill_rate": 45000,
            "cost_rate": 18000,
            "billable": False,
            "status": "submitted",
        },
        # rejetée : DOIT être ignorée intégralement
        {
            "minutes": 999,
            "bill_rate": 45000,
            "cost_rate": 18000,
            "billable": True,
            "status": "rejected",
        },
    ]
    econ = compute_engagement_economics(entries)

    assert econ["entries"] == 2  # la rejetée n'est pas comptée
    assert econ["minutes"] == 600
    assert econ["billable_minutes"] == 480
    assert econ["honoraires"] == 360000
    # honoraires_wip = part billable ET approved uniquement
    assert econ["honoraires_wip"] == 360000
    assert econ["cost"] == 144000 + 36000
    assert econ["margin"] == econ["honoraires"] - econ["cost"]
    assert econ["margin_pct"] == round(econ["margin"] / econ["honoraires"] * 100)
    assert econ["currency"] == "XAF"


def test_compute_engagement_economics_honoraires_wip_excludes_non_approved():
    entries = [
        # facturable mais encore soumise (pas approved) : ne compte PAS dans wip
        {
            "minutes": 240,
            "bill_rate": 45000,
            "cost_rate": 18000,
            "billable": True,
            "status": "submitted",
        },
    ]
    econ = compute_engagement_economics(entries)
    assert econ["honoraires"] == 180000
    assert econ["honoraires_wip"] == 0


def test_compute_engagement_economics_no_honoraires_gives_margin_pct_none():
    entries = [
        {
            "minutes": 60,
            "bill_rate": 0,
            "cost_rate": 0,
            "billable": False,
            "status": "draft",
        }
    ]
    econ = compute_engagement_economics(entries)
    assert econ["honoraires"] == 0
    assert econ["margin_pct"] is None


# ----------------------------------------------------------------------------
# economics.py — compute_utilization
# ----------------------------------------------------------------------------


def test_compute_utilization_occupation_pct():
    available = 20 * 8 * 60  # 20 jours ouvrés x 8h x 60 = 9600
    u = compute_utilization(worked_minutes=4800, billable_minutes=4800, available_minutes=available)
    assert available == 9600
    assert u["occupation_pct"] == 50
    assert u["activity_pct"] == 50


def test_compute_utilization_zero_available_gives_none():
    u = compute_utilization(worked_minutes=100, billable_minutes=50, available_minutes=0)
    assert u["occupation_pct"] is None
    assert u["activity_pct"] is None
