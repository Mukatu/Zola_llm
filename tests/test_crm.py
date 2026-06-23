"""Tests Commercial / CRM (addendum §3.2, CRM-1) — moteur déterministe."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from zolaos.agents.crm.engine import (
    detect_relances,
    pipeline_stats,
    quote_to_invoice,
    score_lead,
)
from zolaos.agents.crm.models import Opportunity, Quote

AS_OF = date(2026, 2, 1)


def _opp(idx: str, montant: str, etape: str, *, derniere: date | None = None) -> Opportunity:
    return Opportunity(
        id_externe=idx,
        client="ACME",
        libelle=f"Deal {idx}",
        montant_xaf=Decimal(montant),
        etape=etape,
        derniere_interaction=derniere,
    )


def _quote(idx: str, statut: str, *, emission: date, validite: date | None) -> Quote:
    return Quote(
        id_externe=idx,
        numero=f"D-{idx}",
        client="ACME",
        date_emission=emission,
        date_validite=validite,
        statut=statut,
        montant_ht_xaf=Decimal("1000"),
        montant_ttc_xaf=Decimal("1180"),
    )


# ------------------------------------------------------------ pipeline


def test_pipeline_stats() -> None:
    opps = [
        _opp("O1", "1000000", "prospection"),
        _opp("O2", "2000000", "negociation"),
        _opp("O3", "3000000", "gagnee"),
        _opp("O4", "500000", "perdue"),
    ]
    s = pipeline_stats(opps)
    assert s.nb_open == 2
    assert s.total_open_xaf == Decimal("3000000")
    assert s.weighted_open_xaf == Decimal("1700000")  # 1e6*0.1 + 2e6*0.8
    assert s.win_rate_pct == Decimal("50.0")
    assert s.par_etape_xaf["negociation"] == Decimal("2000000")


# ------------------------------------------------------------ scoring


def test_score_lead_deterministic() -> None:
    opp = _opp("O", "5000000", "negociation", derniere=AS_OF)  # récent
    score = score_lead(opp, as_of=AS_OF)
    # 0.40*0.80 + 0.25*1.0 + 0.20*0.5 + 0.15*0.4 = 0.73
    assert score.score == 73
    assert score.grade == "B"


def test_score_lead_low_for_cold_prospection() -> None:
    opp = _opp("O", "0", "prospection", derniere=date(2025, 1, 1))  # vieux, faible
    score = score_lead(opp, as_of=AS_OF)
    assert score.grade in ("C", "D")


# ------------------------------------------------------------ relances


def test_detect_relances() -> None:
    quotes = [
        _quote("Q1", "envoye", emission=date(2026, 1, 1), validite=date(2026, 1, 15)),  # expiré
        _quote(
            "Q2", "envoye", emission=date(2026, 1, 5), validite=date(2026, 3, 1)
        ),  # sans réponse
        _quote("Q3", "accepte", emission=date(2026, 1, 5), validite=date(2026, 3, 1)),  # ignoré
    ]
    opps = [
        _opp("O1", "6000000", "negociation", derniere=date(2026, 1, 1)),  # froid, gros → high
        _opp("O2", "100", "gagnee", derniere=date(2026, 1, 1)),  # fermé → ignoré
    ]
    items = detect_relances(quotes, opps, as_of=AS_OF, seuil_jours=14)
    types = sorted(i.type for i in items)
    assert types == ["devis_expire", "devis_relance", "opportunite"]
    expire = next(i for i in items if i.type == "devis_expire")
    assert expire.priorite == "high"
    opp_item = next(i for i in items if i.type == "opportunite")
    assert opp_item.priorite == "high"  # montant >= 5M


# ------------------------------------------------------------ devis→facture


def test_quote_to_invoice_accepted() -> None:
    q = _quote("Q", "accepte", emission=date(2026, 1, 5), validite=date(2026, 3, 1))
    inv = quote_to_invoice(q)
    assert inv.sens == "vente"
    assert inv.tiers == "ACME"
    assert inv.montant_ttc_xaf == Decimal("1180")
    assert inv.payee is False


def test_quote_to_invoice_rejects_non_accepted() -> None:
    q = _quote("Q", "envoye", emission=date(2026, 1, 5), validite=date(2026, 3, 1))
    with pytest.raises(ValueError):
        quote_to_invoice(q)
