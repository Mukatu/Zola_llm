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
from typing import Any

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


class Regime(BaseModel):
    """Régime d'imposition des salaires (IRPP ≤2025, ITS ≥2026) — PAIE-4."""

    label: str = ""
    bareme: list[IrppTranche] = Field(default_factory=list)


class CnssBranche(BaseModel):
    """Branche de cotisation CNSS, avec assiette plafonnée propre — PAIE-4."""

    nom: str
    label: str = ""
    taux_salarie: Decimal = Field(default=_ZERO, ge=0, le=1)
    taux_employeur: Decimal = Field(default=_ZERO, ge=0, le=1)
    plafond_mensuel_xaf: Decimal | None = None


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
    # Forfaits annuels DAS 1 par salarié (taxe régionale, TOL/CAMU) — 0 ⇒ à sourcer
    taxe_regionale_annuelle_xaf: Decimal = Field(default=_ZERO, ge=0)
    tol_camu_annuel_xaf: Decimal = Field(default=_ZERO, ge=0)

    # --- structure sourcée PAIE-4 (optionnelle ; active le calcul régime + parts) ---
    regimes: dict[str, Regime] = Field(default_factory=dict)
    regime_its_depuis_annee: int = 2026
    impot_minimum_annuel_xaf: Decimal = Field(default=_ZERO, ge=0)
    plafond_parts: Decimal = Field(default=Decimal("6.5"), gt=0)
    cnss_branches: list[CnssBranche] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    autres_charges_patronales_a_confirmer: list[dict[str, Any]] = Field(default_factory=list)

    def regime_pour_annee(self, annee: int) -> Regime | None:
        """Régime applicable à l'exercice (ITS dès `regime_its_depuis_annee`)."""
        if not self.regimes:
            return None
        cle = "its" if annee >= self.regime_its_depuis_annee else "irpp"
        return self.regimes.get(cle)


def parts_fiscales(
    situation_matrimoniale: str, nb_enfants: int, *, plafond: Decimal = Decimal("6.5")
) -> Decimal:
    """Quotient familial CG : 2 parts si marié sinon 1, +0,5 par enfant, plafonné.

    Simplification documentée : la majoration « 1er enfant d'un parent isolé »
    n'est pas distinguée (à affiner avec la convention applicable). PAIE-4.
    """
    base = Decimal("2") if situation_matrimoniale.strip().lower() == "marie" else Decimal("1")
    parts = base + Decimal("0.5") * Decimal(max(0, nb_enfants))
    return min(parts, plafond)


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


def load_payroll_scale_dict(country: str = "cg") -> dict[str, Any]:
    """Charge le barème brut (graine) depuis `ref/payroll_<country>.json`."""
    path = _REF_DIR / f"payroll_{country}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Barème de paie introuvable pour {country!r} : {path}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def load_payroll_scale(country: str = "cg") -> PayrollScale:
    """Charge le barème (graine) depuis `ref/payroll_<country>.json`."""
    return PayrollScale.model_validate(load_payroll_scale_dict(country))


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

    @staticmethod
    def _cotisations_par_branche(
        brut: Decimal, branches: list[CnssBranche]
    ) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
        """Cotisations salariales/patronales par branche CNSS (assiette plafonnée propre)."""
        cot_sal: dict[str, Decimal] = {}
        cot_pat: dict[str, Decimal] = {}
        for br in branches:
            assiette = _plafonne(brut, br.plafond_mensuel_xaf)
            cot_sal[br.nom] = _xaf(assiette * br.taux_salarie)
            cot_pat[br.nom] = _xaf(assiette * br.taux_employeur)
        return cot_sal, cot_pat

    @staticmethod
    def _impot_avec_parts(
        base_mensuelle: Decimal,
        bareme: list[IrppTranche],
        parts: Decimal,
        minimum_annuel: Decimal,
    ) -> Decimal:
        """Impôt mensuel = barème annuel appliqué à la base par part × parts ÷ 12.

        Séquence officielle CG : annualisation → quotient familial → barème
        progressif par part → reconstitution → mensualisation.
        """
        parts = parts if parts > 0 else Decimal("1")
        base_annuelle = base_mensuelle * 12
        base_par_part = base_annuelle / parts
        impot_par_part = _irpp(base_par_part, bareme)
        impot_annuel = impot_par_part * parts
        if base_annuelle > 0:
            impot_annuel = max(impot_annuel, minimum_annuel)
        return _xaf(impot_annuel / 12)

    def compute(
        self,
        brut_mensuel_xaf: Decimal,
        *,
        scale: PayrollScale,
        allow_unvalidated: bool = False,
        parts: Decimal = Decimal("1"),
        annee: int | None = None,
    ) -> PayrollResult:
        """Calcule un bulletin. Lève `PayrollScaleNotValidated` si barème non validé.

        Si le barème porte des `cnss_branches` et/ou des `regimes` (PAIE-4), le
        calcul utilise les branches CNSS plafonnées par assiette et l'impôt par
        régime (IRPP/ITS selon `annee`) avec quotient familial (`parts`). Sinon il
        retombe sur le calcul historique à barème plat (rétrocompatible).
        """
        if not scale.validated and not allow_unvalidated:
            raise PayrollScaleNotValidated(
                f"Barème {scale.country}/{scale.version} non validé : émission de bulletin "
                "refusée (passer allow_unvalidated=True pour une simulation explicite)."
            )
        if brut_mensuel_xaf < 0:
            raise ValueError("Le salaire brut ne peut être négatif.")

        brut = brut_mensuel_xaf

        # --- cotisations salariales + patronales ---
        if scale.cnss_branches:
            cot_sal, cot_pat = self._cotisations_par_branche(brut, scale.cnss_branches)
        else:
            assiette_cnss = _plafonne(brut, scale.cnss_plafond_xaf)
            cot_sal = {
                "cnss": _xaf(assiette_cnss * scale.cnss_salarie_taux),
                "cipres": _xaf(brut * scale.cipres_salarie_taux),
            }
            cot_pat = {
                "cnss_employeur": _xaf(assiette_cnss * scale.cnss_employeur_taux),
                "allocations_familiales": _xaf(brut * scale.allocations_familiales_taux),
                "accident_travail": _xaf(brut * scale.accident_travail_taux),
                "taxe_sur_salaires": _xaf(brut * scale.taxe_sur_salaires_taux),
            }
        cot_sal = {k: v for k, v in cot_sal.items() if v > 0}
        cot_pat = {k: v for k, v in cot_pat.items() if v > 0}
        total_cot_sal = sum(cot_sal.values(), _ZERO)

        # --- base imposable ---
        base_brute = brut - total_cot_sal
        abattement = _xaf(base_brute * scale.abattement_irpp_taux)
        base_imposable = max(_ZERO, base_brute - abattement)

        # --- impôt (IRPP/ITS) ---
        regime = scale.regime_pour_annee(annee) if annee is not None else None
        if regime is not None and regime.bareme:
            irpp = self._impot_avec_parts(
                base_imposable, regime.bareme, parts, scale.impot_minimum_annuel_xaf
            )
        else:
            irpp = _xaf(_irpp(base_imposable, scale.irpp_bareme))

        net = brut - total_cot_sal - irpp
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
