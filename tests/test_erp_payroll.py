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
    IrppTranche,
    PayrollCalculator,
    PayrollScale,
    PayrollScaleNotValidated,
    _irpp,
    load_payroll_scale,
)


def _simple_scale(**overrides) -> PayrollScale:
    base = dict(
        validated=True,
        cnss_salarie_taux=Decimal("0.04"),
        cnss_employeur_taux=Decimal("0.08"),
        cnss_plafond_xaf=None,
        cipres_salarie_taux=Decimal("0"),
        abattement_irpp_taux=Decimal("0"),
        irpp_bareme=[IrppTranche(plafond_xaf=None, taux=Decimal("0.10"))],
    )
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
    assert res.irpp_xaf == Decimal("9600")          # 96000 * 0.10
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
