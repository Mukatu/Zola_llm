"""BI v2 — signaux déterministes + échéances indicatives."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from zolaos.agents.bi.echeances import prochaines_echeances
from zolaos.agents.bi.kpi import KpiValue
from zolaos.agents.bi.signals import compute_signals


def _kpi(code: str, valeur: str, unite: str = "XAF", domaine: str = "finance") -> KpiValue:
    return KpiValue(code=code, libelle=code, valeur=Decimal(valeur), unite=unite, domaine=domaine)


def test_signal_tresorerie_negative() -> None:
    sig = compute_signals([_kpi("position_tresorerie", "-500000")])
    codes = {s.code: s.niveau for s in sig}
    assert codes.get("tresorerie_negative") == "alerte"


def test_signal_marge_faible() -> None:
    sig = compute_signals(
        [_kpi("ca_ht", "1000000", domaine="commercial"), _kpi("marge_brute", "100000")]
    )
    assert any(s.code == "marge_faible" and s.niveau == "attention" for s in sig)


def test_signal_marge_negative_prioritaire() -> None:
    sig = compute_signals([_kpi("ca_ht", "1000000"), _kpi("marge_brute", "-50000")])
    assert any(s.code == "marge_negative" and s.niveau == "alerte" for s in sig)
    assert not any(s.code == "marge_faible" for s in sig)


def test_signal_dso_paliers() -> None:
    assert any(s.code == "dso_alerte" for s in compute_signals([_kpi("dso", "95", "jours")]))
    assert any(s.code == "dso_attention" for s in compute_signals([_kpi("dso", "65", "jours")]))


def test_signal_ras_si_sain() -> None:
    sig = compute_signals(
        [_kpi("ca_ht", "1000000"), _kpi("marge_brute", "400000"), _kpi("dso", "20", "jours")]
    )
    assert sig[0].code == "ras" and sig[0].niveau == "info"


def test_echeances_triees_et_indicatives() -> None:
    ech = prochaines_echeances(date(2026, 7, 7))
    assert ech, "au moins une échéance dans l'horizon"
    assert all(e.indicatif for e in ech)
    assert all(e.jours_restants >= 0 for e in ech)
    dates = [e.date_limite for e in ech]
    assert dates == sorted(dates)


def test_echeance_mensuelle_bascule_mois_suivant() -> None:
    # le 25 : la TVA (jour 20) est passée ce mois → bascule au mois suivant.
    ech = {e.code: e for e in prochaines_echeances(date(2026, 7, 25))}
    assert ech["tva"].date_limite == date(2026, 8, 20)
