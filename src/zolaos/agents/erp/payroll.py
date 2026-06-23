"""Moteur de paie déterministe — pôle ERP, RH-2 (V2.2 §4.1/§4.3).

Calcul **100% déterministe** d'un bulletin de paie : brut → cotisations
salariales → base imposable → IRPP → net, + coût employeur (cotisations
patronales). **Aucun LLM** : pour un calcul de paie, la donnée *est* la logique.

Les barèmes (taux CNSS/CIPRES, plafond, IRPP, SMIG…) sont des **paramètres**
chargés depuis une ressource `ref` (`ref/payroll_<pays>.json`), jamais en dur.

### Verrou de validation (sûr par défaut)
Un barème porte `validated`. `compute()` **refuse** d'émettre un bulletin si
`validated=false`, sauf `allow_unvalidated=True` (tests / simulation explicite).
→ Impossible d'émettre une paie avec des taux non vérifiés par accident
(directive §5.7 : validation humaine sur RH/fiscal avant production).

Brancher des barèmes vérifiés = remplacer des valeurs dans la ressource `ref`
+ passer `validated=true`. Zéro réécriture de code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pydantic import BaseModel, Field

_REF_DIR = Path(__file__).parent / "ref"
_ZERO = Decimal("0")


def _xaf(v: Decimal) -> Decimal:
    """Arrondi au franc CFA entier (pas de centime en XAF)."""
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class PayrollScaleNotValidated(RuntimeError):
    """Tentative de calcul de paie sur un barème non validé."""


class IrppTranche(BaseModel):
    plafond_xaf: Decimal | None = Field(
        default=None, description="Borne haute (None = tranche ouverte)"
    )
    taux: Decimal = Field(..., ge=0, le=1)


class PayrollScale(BaseModel):
    """Barème de paie paramétrable (ressource `ref`)."""

    model_config = {"extra": "ignore"}

    country: str = Field(default="cg", pattern=r"^[a-z]{2}$")
    version: str = "placeholder"
    source: str = ""
    validated: bool = False

    smig_xaf: Decimal = _ZERO
    cnss_salarie_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    cnss_employeur_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    cnss_plafond_xaf: Decimal | None = None
    cipres_salarie_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    allocations_familiales_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    accident_travail_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    taxe_sur_salaires_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    abattement_irpp_taux: Decimal = Field(default=_ZERO, ge=0, le=1)
    irpp_bareme: list[IrppTranche] = Field(default_factory=list)


@dataclass(frozen=True)
class PayrollResult:
    brut_xaf: Decimal
    cotisations_salariales: dict[str, Decimal]
    total_cotisations_salariales_xaf: Decimal
    base_imposable_xaf: Decimal
    irpp_xaf: Decimal
    net_a_payer_xaf: Decimal
    cotisations_patronales: dict[str, Decimal]
    cout_employeur_xaf: Decimal
    barème_validé: bool = field(default=False)


def load_payroll_scale(country: str = "cg") -> PayrollScale:
    """Charge le barème depuis `ref/payroll_<country>.json`."""
    path = _REF_DIR / f"payroll_{country}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Barème de paie introuvable pour {country!r} : {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PayrollScale.model_validate(data)


def _plafonne(base: Decimal, plafond: Decimal | None) -> Decimal:
    return min(base, plafond) if plafond is not None else base


def _irpp(base_imposable: Decimal, bareme: list[IrppTranche]) -> Decimal:
    """Barème progressif par tranches (la dernière `plafond_xaf=None` est ouverte)."""
    tax = _ZERO
    lower = _ZERO
    for tranche in bareme:
        if base_imposable <= lower:
            break
        upper = tranche.plafond_xaf if tranche.plafond_xaf is not None else base_imposable
        portion = _plafonne(base_imposable, upper) - lower
        if portion > 0:
            tax += portion * tranche.taux
        lower = upper
    return tax


class PayrollCalculator:
    """Calculateur de paie déterministe (paramétré par un `PayrollScale`)."""

    name = "erp.payroll"

    def compute(
        self,
        brut_mensuel_xaf: Decimal,
        *,
        scale: PayrollScale,
        allow_unvalidated: bool = False,
    ) -> PayrollResult:
        """Calcule un bulletin. Lève `PayrollScaleNotValidated` si barème non validé."""
        if not scale.validated and not allow_unvalidated:
            raise PayrollScaleNotValidated(
                f"Barème {scale.country}/{scale.version} non validé : émission de bulletin "
                "refusée (passer allow_unvalidated=True pour une simulation explicite)."
            )
        if brut_mensuel_xaf < 0:
            raise ValueError("Le salaire brut ne peut être négatif.")

        brut = brut_mensuel_xaf
        assiette_cnss = _plafonne(brut, scale.cnss_plafond_xaf)

        # --- cotisations salariales ---
        cot_sal: dict[str, Decimal] = {
            "cnss": _xaf(assiette_cnss * scale.cnss_salarie_taux),
            "cipres": _xaf(brut * scale.cipres_salarie_taux),
        }
        cot_sal = {k: v for k, v in cot_sal.items() if v > 0}
        total_cot_sal = sum(cot_sal.values(), _ZERO)

        # --- base imposable IRPP ---
        base_brute = brut - total_cot_sal
        abattement = _xaf(base_brute * scale.abattement_irpp_taux)
        base_imposable = max(_ZERO, base_brute - abattement)
        irpp = _xaf(_irpp(base_imposable, scale.irpp_bareme))

        net = brut - total_cot_sal - irpp

        # --- cotisations patronales (coût employeur, non déduites du net) ---
        cot_pat: dict[str, Decimal] = {
            "cnss_employeur": _xaf(assiette_cnss * scale.cnss_employeur_taux),
            "allocations_familiales": _xaf(brut * scale.allocations_familiales_taux),
            "accident_travail": _xaf(brut * scale.accident_travail_taux),
            "taxe_sur_salaires": _xaf(brut * scale.taxe_sur_salaires_taux),
        }
        cot_pat = {k: v for k, v in cot_pat.items() if v > 0}
        cout_employeur = brut + sum(cot_pat.values(), _ZERO)

        return PayrollResult(
            brut_xaf=_xaf(brut),
            cotisations_salariales=cot_sal,
            total_cotisations_salariales_xaf=_xaf(total_cot_sal),
            base_imposable_xaf=_xaf(base_imposable),
            irpp_xaf=irpp,
            net_a_payer_xaf=_xaf(net),
            cotisations_patronales=cot_pat,
            cout_employeur_xaf=_xaf(cout_employeur),
            barème_validé=scale.validated,
        )
