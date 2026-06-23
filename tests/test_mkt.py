"""Tests Marketing MKT-1 : segmentation + consentement (Loi 29-2019) déterministes."""

from __future__ import annotations

from datetime import date

import pytest

from zolaos.agents.mkt.consent import (
    ConsentError,
    consent_summary,
    ensure_consent,
    filter_consented,
    is_eligible,
)
from zolaos.agents.mkt.models import MarketingContact
from zolaos.agents.mkt.segmentation import recency_bucket, segment_contacts

AS_OF = date(2026, 2, 1)


def _c(
    idx: str,
    *,
    type_: str = "client",
    derniere: date | None = None,
    consent: bool = False,
    finalites: list[str] | None = None,
) -> MarketingContact:
    return MarketingContact(
        id_externe=idx,
        nom=f"C{idx}",
        type=type_,
        derniere_interaction=derniere,
        consentement_marketing=consent,
        finalites=finalites or [],
    )


def test_recency_buckets() -> None:
    assert recency_bucket(_c("a", derniere=date(2026, 1, 20)), AS_OF) == "actif"
    assert recency_bucket(_c("b", derniere=date(2025, 12, 15)), AS_OF) == "recent"
    assert recency_bucket(_c("c", derniere=date(2025, 6, 1)), AS_OF) == "dormant"
    assert recency_bucket(_c("d", derniere=None), AS_OF) == "inactif"


def test_segment_contacts() -> None:
    contacts = [
        _c("1", type_="client", derniere=date(2026, 1, 20)),
        _c("2", type_="prospect", derniere=None),
    ]
    seg = segment_contacts(contacts, as_of=AS_OF)
    assert "client_actif" in seg
    assert "prospect_inactif" in seg
    assert seg["client_actif"][0].id_externe == "1"


def test_consent_eligibility() -> None:
    ok = _c("1", consent=True, finalites=["newsletter", "promotions"])
    no_consent = _c("2", consent=False, finalites=["newsletter"])
    wrong_finalite = _c("3", consent=True, finalites=["promotions"])
    assert is_eligible(ok, "newsletter")
    assert not is_eligible(no_consent, "newsletter")
    assert not is_eligible(wrong_finalite, "newsletter")


def test_filter_and_summary() -> None:
    contacts = [
        _c("1", consent=True, finalites=["newsletter"]),
        _c("2", consent=False, finalites=["newsletter"]),
        _c("3", consent=True, finalites=["promotions"]),
    ]
    eligibles = filter_consented(contacts, "newsletter")
    assert [c.id_externe for c in eligibles] == ["1"]
    s = consent_summary(contacts, "newsletter")
    assert (s.eligibles, s.exclus, s.total) == (1, 2, 3)


def test_ensure_consent_raises() -> None:
    with pytest.raises(ConsentError):
        ensure_consent(_c("x", consent=False), "newsletter")
