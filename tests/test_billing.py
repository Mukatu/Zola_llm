"""Tests unitaires du moteur de facturation (`zolaos.billing`).

Couvre :
- `load_pricing` : défauts à zéro, surcharge via `BILLING_PRICING_JSON`, JSON vide
  ou invalide (retombe sur zéro sans lever)
- `compute_bill` : forfait + dépassement par tranche de 1000 requêtes ; tier
  inconnu/None → coût 0
- `record_usage_durable` : upsert cumulatif sur `core.usage_daily` (PK composite
  tenant_id/day)
"""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from zolaos.billing.ledger import record_usage_durable
from zolaos.billing.pricing import compute_bill, load_pricing
from zolaos.db.session import get_session_factory, reset_engine_cache

_BUSINESS_PRICING_JSON = (
    '{"business": {"monthly_base": 150000, "included_requests": 50000, '
    '"overage_per_1k": 500, "currency": "XAF"}}'
)


# ----------------------------------------------------------------------------
# load_pricing
# ----------------------------------------------------------------------------
def test_load_pricing_defaults_to_zero_for_every_tier() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=""))
    assert pricing  # au moins les tiers connus
    for price in pricing.values():
        assert price["monthly_base"] == 0
        assert price["included_requests"] == 0
        assert price["overage_per_1k"] == 0
        assert price["currency"] == "XAF"


def test_load_pricing_empty_json_yields_zeros() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON="{}"))
    for price in pricing.values():
        assert price["monthly_base"] == 0
        assert price["overage_per_1k"] == 0


def test_load_pricing_invalid_json_falls_back_to_zero() -> None:
    # Ne doit JAMAIS lever — un barème mal formé ne casse pas la facturation.
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON="{not valid json"))
    for price in pricing.values():
        assert price["monthly_base"] == 0


def test_load_pricing_applies_override_for_named_tier() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=_BUSINESS_PRICING_JSON))
    assert pricing["business"]["monthly_base"] == 150000
    assert pricing["business"]["included_requests"] == 50000
    assert pricing["business"]["overage_per_1k"] == 500
    assert pricing["business"]["currency"] == "XAF"


# ----------------------------------------------------------------------------
# compute_bill
# ----------------------------------------------------------------------------
def test_compute_bill_zero_pricing_stays_zero_even_with_heavy_usage() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=""))
    bill = compute_bill("business", requests=1_000_000, tokens=50_000_000, pricing=pricing)
    assert bill["total"] == 0
    assert bill["monthly_base"] == 0
    assert bill["overage_cost"] == 0


def test_compute_bill_applies_base_plus_overage() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=_BUSINESS_PRICING_JSON))
    bill = compute_bill("business", requests=62_000, tokens=0, pricing=pricing)
    assert bill["overage_requests"] == 12_000
    assert bill["overage_cost"] == 6_000
    assert bill["total"] == 156_000
    assert bill["monthly_base"] == 150_000
    assert bill["currency"] == "XAF"


def test_compute_bill_within_included_quota_has_no_overage() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=_BUSINESS_PRICING_JSON))
    bill = compute_bill("business", requests=10_000, tokens=0, pricing=pricing)
    assert bill["overage_requests"] == 0
    assert bill["overage_cost"] == 0
    assert bill["total"] == 150_000


def test_compute_bill_unknown_tier_is_zero() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=_BUSINESS_PRICING_JSON))
    bill = compute_bill("does-not-exist", requests=100_000, tokens=0, pricing=pricing)
    assert bill["total"] == 0


def test_compute_bill_none_tier_is_zero() -> None:
    pricing = load_pricing(SimpleNamespace(BILLING_PRICING_JSON=_BUSINESS_PRICING_JSON))
    bill = compute_bill(None, requests=100_000, tokens=0, pricing=pricing)
    assert bill["total"] == 0


# ----------------------------------------------------------------------------
# record_usage_durable (grand livre — DB)
# ----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    reset_engine_cache()
    yield
    reset_engine_cache()


@pytest.mark.asyncio
async def test_record_usage_durable_upserts_and_cumulates() -> None:
    factory = get_session_factory()
    tenant_id = f"test-ledger-{uuid.uuid4().hex[:10]}"
    day = date(2019, 3, 1)

    try:
        async with factory() as s:
            await record_usage_durable(s, tenant_id=tenant_id, day=day, requests=1, tokens=10)
            await s.commit()

        async with factory() as s:
            await record_usage_durable(s, tenant_id=tenant_id, day=day, requests=1, tokens=5)
            await s.commit()

        async with factory() as s:
            row = (
                await s.execute(
                    text(
                        "SELECT requests, tokens FROM core.usage_daily "
                        "WHERE tenant_id = :t AND day = :d"
                    ),
                    {"t": tenant_id, "d": day},
                )
            ).one()
            assert row.requests == 2
            assert row.tokens == 15
    finally:
        async with factory() as s:
            await s.execute(
                text("DELETE FROM core.usage_daily WHERE tenant_id = :t"), {"t": tenant_id}
            )
            await s.commit()
