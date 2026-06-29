"""Tests du moteur de paie déterministe (ERP RH-2).

- Verrou de validation : refus si barème non validé.
- Calcul déterministe exact (cotisations, base, IRPP, net, coût employeur).
- Barème IRPP progressif.
- Plafond CNSS.
- Le seed `ref` est bien flaggé non validé.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from zolaos.agents.erp.payroll import (
    CnssBranche,
    IrppTranche,
    PayrollCalculator,
    PayrollScale,
    PayrollScaleNotValidated,
    Regime,
    Rubrique,
    _irpp,
    load_payroll_scale,
    parts_fiscales,
)


def _simple_scale(**overrides) -> PayrollScale:
    base = {
        "validated": True,
        "cnss_salarie_taux": Decimal("0.04"),
        "cnss_employeur_taux": Decimal("0.08"),
        "cnss_plafond_xaf": None,
        "cipres_salarie_taux": Decimal("0"),
        "abattement_irpp_taux": Decimal("0"),
        "irpp_bareme": [IrppTranche(plafond_xaf=None, taux=Decimal("0.10"))],
    }
    base.update(overrides)
    return PayrollScale(**base)


def test_seed_is_flagged_unvalidated() -> None:
    scale = load_payroll_scale("cg")
    assert scale.validated is False
    assert scale.smig_xaf == Decimal("70400")


def test_validation_gate_blocks_unvalidated() -> None:
    scale = load_payroll_scale("cg")  # validated=False
    calc = PayrollCalculator()
    with pytest.raises(PayrollScaleNotValidated):
        calc.compute(Decimal("150000"), scale=scale)
    # Simulation explicite autorisée
    res = calc.compute(Decimal("150000"), scale=scale, allow_unvalidated=True)
    assert res.barème_validé is False
    assert res.brut_xaf == Decimal("150000")


def test_deterministic_payslip_math() -> None:
    calc = PayrollCalculator()
    res = calc.compute(Decimal("100000"), scale=_simple_scale())
    assert res.cotisations_salariales["cnss"] == Decimal("4000")
    assert res.total_cotisations_salariales_xaf == Decimal("4000")
    assert res.base_imposable_xaf == Decimal("96000")
    assert res.irpp_xaf == Decimal("9600")  # 96000 * 0.10
    assert res.net_a_payer_xaf == Decimal("86400")  # 100000 - 4000 - 9600
    assert res.cotisations_patronales["cnss_employeur"] == Decimal("8000")
    assert res.cout_employeur_xaf == Decimal("108000")
    assert res.cout_employeur_xaf > res.brut_xaf


def test_irpp_progressive_brackets() -> None:
    bareme = [
        IrppTranche(plafond_xaf=Decimal("464000"), taux=Decimal("0.01")),
        IrppTranche(plafond_xaf=Decimal("1000000"), taux=Decimal("0.10")),
        IrppTranche(plafond_xaf=None, taux=Decimal("0.25")),
    ]
    # 464000*0.01 + 536000*0.10 + 500000*0.25 = 4640 + 53600 + 125000
    assert _irpp(Decimal("1500000"), bareme) == Decimal("183240")
    # Sous la première borne : seulement 1%
    assert _irpp(Decimal("100000"), bareme) == Decimal("1000")
    assert _irpp(Decimal("0"), bareme) == Decimal("0")


def test_cnss_plafond_caps_assiette() -> None:
    calc = PayrollCalculator()
    res = calc.compute(Decimal("100000"), scale=_simple_scale(cnss_plafond_xaf=Decimal("50000")))
    assert res.cotisations_salariales["cnss"] == Decimal("2000")  # 50000 * 0.04, plafonné


def test_negative_brut_rejected() -> None:
    with pytest.raises(ValueError):
        PayrollCalculator().compute(Decimal("-1"), scale=_simple_scale())


# ---------------------------------------------------------------- PAIE-4 (barème sourcé)


def test_seed_cg_structure_sourcee() -> None:
    """Le barème cg embarque les deux régimes et les branches CNSS, et reste non validé."""
    scale = load_payroll_scale("cg")
    assert scale.validated is False
    assert set(scale.regimes) == {"irpp", "its"}
    assert scale.regime_its_depuis_annee == 2026
    noms = {b.nom for b in scale.cnss_branches}
    assert {"retraite_pvid", "allocations_familiales", "accidents_travail"} <= noms


def test_parts_fiscales() -> None:
    assert parts_fiscales("celibataire", 0) == Decimal("1")
    assert parts_fiscales("marie", 0) == Decimal("2")
    assert parts_fiscales("marie", 2) == Decimal("3")  # 2 + 0,5×2
    assert parts_fiscales("marie", 20) == Decimal("6.5")  # plafonné


def test_cnss_branches_assiettes_distinctes() -> None:
    """Chaque branche CNSS a son propre plafond (retraite 1,2M, AF/AT 600k)."""
    branches = [
        CnssBranche(
            nom="retraite_pvid",
            taux_salarie="0.04",
            taux_employeur="0.08",
            plafond_mensuel_xaf="1200000",
        ),
        CnssBranche(
            nom="allocations_familiales", taux_employeur="0.1003", plafond_mensuel_xaf="600000"
        ),
        CnssBranche(nom="accidents_travail", taux_employeur="0.0225", plafond_mensuel_xaf="600000"),
    ]
    scale = PayrollScale(validated=True, abattement_irpp_taux="0", cnss_branches=branches)
    res = PayrollCalculator().compute(Decimal("1000000"), scale=scale)
    # salarié : retraite 4 % sur 1 000 000 (< plafond) = 40 000
    assert res.cotisations_salariales["retraite_pvid"] == Decimal("40000")
    # patronal : 8 % sur 1M + 10,03 % sur 600k + 2,25 % sur 600k
    assert res.cotisations_patronales["retraite_pvid"] == Decimal("80000")
    assert res.cotisations_patronales["allocations_familiales"] == Decimal("60180")
    assert res.cotisations_patronales["accidents_travail"] == Decimal("13500")


def _regime_scale() -> PayrollScale:
    irpp = Regime(
        bareme=[
            IrppTranche(plafond_xaf="464000", taux="0.01"),
            IrppTranche(plafond_xaf="1000000", taux="0.10"),
            IrppTranche(plafond_xaf="3000000", taux="0.25"),
            IrppTranche(plafond_xaf=None, taux="0.40"),
        ]
    )
    its = Regime(
        bareme=[
            IrppTranche(plafond_xaf="615000", taux="0.00"),
            IrppTranche(plafond_xaf="1500000", taux="0.10"),
            IrppTranche(plafond_xaf="3500000", taux="0.15"),
            IrppTranche(plafond_xaf="5000000", taux="0.20"),
            IrppTranche(plafond_xaf=None, taux="0.30"),
        ]
    )
    return PayrollScale(
        validated=True,
        cnss_salarie_taux="0.04",
        cnss_plafond_xaf="1200000",
        abattement_irpp_taux="0.20",
        regimes={"irpp": irpp, "its": its},
        regime_its_depuis_annee=2026,
        impot_minimum_annuel_xaf="1200",
    )


def test_regime_irpp_vs_its_par_annee() -> None:
    """Même brut, l'exercice ≤2025 applique l'IRPP, ≥2026 l'ITS (impôt différent)."""
    calc = PayrollCalculator()
    scale = _regime_scale()
    # base imposable mensuelle = (500000 − 20000) × 0,8 = 384 000 ; annuelle 4 608 000 ; 1 part
    irpp = calc.compute(Decimal("500000"), scale=scale, parts=Decimal("1"), annee=2025)
    its = calc.compute(Decimal("500000"), scale=scale, parts=Decimal("1"), annee=2026)
    assert irpp.irpp_xaf == Decimal("100120")  # barème IRPP annualisé /12
    assert its.irpp_xaf == Decimal("50842")  # barème ITS annualisé /12
    assert its.irpp_xaf < irpp.irpp_xaf


def test_quotient_familial_reduit_impot() -> None:
    """Le quotient familial (parts) réduit l'impôt à brut égal."""
    calc = PayrollCalculator()
    scale = _regime_scale()
    seul = calc.compute(Decimal("500000"), scale=scale, parts=Decimal("1"), annee=2026)
    famille = calc.compute(Decimal("500000"), scale=scale, parts=Decimal("3"), annee=2026)
    assert seul.irpp_xaf == Decimal("50842")
    assert famille.irpp_xaf == Decimal("23475")  # base/part = 1 536 000
    assert famille.irpp_xaf < seul.irpp_xaf


def test_rubriques_gain_et_retenue() -> None:
    """PAIE-6b : une prime imposable+CNSS et une retenue impactent base, cotis et net."""
    calc = PayrollCalculator()
    rubriques = [
        Rubrique(
            code="prime_rendement",
            type="gain",
            mode="fixe",
            valeur="50000",
            imposable=True,
            soumis_cnss=True,
        ),
        Rubrique(code="prime_transport", type="gain", mode="fixe", valeur="20000"),  # non impos.
        Rubrique(code="avance", type="retenue", mode="fixe", valeur="10000"),
    ]
    scale = _simple_scale(rubriques=rubriques)  # cnss 4 %, abattement 0, irpp 10 %
    res = calc.compute(Decimal("100000"), scale=scale)
    # CNSS sur brut + prime soumise = 150 000 × 4 % = 6 000
    assert res.cotisations_salariales["cnss"] == Decimal("6000")
    # brut imposable = 100 000 + 50 000 = 150 000 ; base = 150 000 − 6 000 = 144 000
    assert res.brut_xaf == Decimal("150000")
    assert res.base_imposable_xaf == Decimal("144000")
    assert res.irpp_xaf == Decimal("14400")  # 144 000 × 10 %
    # net = 100 000 + (50 000+20 000) − 6 000 − 14 400 − 10 000 = 139 600
    assert res.net_a_payer_xaf == Decimal("139600")
    assert res.rubriques["prime_transport"] == Decimal("20000")
    assert res.rubriques["avance"] == Decimal("-10000")


def test_sans_rubrique_calcul_inchange() -> None:
    """Sans rubrique, le calcul reste identique à l'historique (rétrocompatible)."""
    res = PayrollCalculator().compute(Decimal("100000"), scale=_simple_scale())
    assert res.brut_xaf == Decimal("100000")
    assert res.base_imposable_xaf == Decimal("96000")
    assert res.rubriques == {}
