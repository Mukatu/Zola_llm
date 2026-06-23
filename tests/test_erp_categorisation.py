"""Tests auto-catégorisation assistée (libellé → compte SYSCOHADA)."""

from __future__ import annotations

from zolaos.agents.erp.categorisation import suggest_accounts
from zolaos.agents.erp.compta import ChartOfAccounts

_CHART = ChartOfAccounts.load("cg")


def test_loyer_suggere_622() -> None:
    s = suggest_accounts("Loyer du local commercial", chart=_CHART)
    assert s[0].compte == "622"


def test_vente_suggere_701() -> None:
    s = suggest_accounts("Vente de marchandises à crédit", chart=_CHART, sens="credit")
    assert s[0].compte == "701"


def test_salaire_suggere_661() -> None:
    s = suggest_accounts("Salaire employé juin", chart=_CHART, sens="debit")
    assert s[0].compte == "661"


def test_tva_collectee_suggere_4431() -> None:
    s = suggest_accounts("TVA collectée sur ventes", chart=_CHART)
    assert s[0].compte == "4431"


def test_inconnu_retourne_vide() -> None:
    assert suggest_accounts("xyzzy blurp wibble", chart=_CHART) == []


def test_endpoint_suggest(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post(
        "/v1/erp/compta/suggest", json={"libelle": "Paiement du loyer", "sens": "debit"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["suggestions"][0]["compte"] == "622"
    assert "raison" in body["suggestions"][0]
