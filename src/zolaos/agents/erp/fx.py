"""Change / multi-devise — conversion déterministe **gouvernée** (P3, MULTIDEV-1).

Le XAF (franc CFA BEAC) est la **devise de référence** de tout le système : les
montants persistés (`*_xaf`) sont canoniquement en XAF. Ce module fournit une
table de taux gouvernée (graine `ref/fx_rates_<pays>.json` + override tenant) et
une conversion **déterministe** : ``montant_xaf = montant × taux_vers_xaf``.

Gouvernance (même esprit que le barème de paie) : chaque taux porte ``validated``.
Un taux non validé ne peut pas servir à une conversion — la fonction s'abstient
(`FxRateNotValidated`). La parité EUR est fixe et officielle (1 EUR = 655,957
XAF, garantie BEAC) donc validée d'origine ; les devises flottantes (USD, GBP,
CNY…) sont livrées **non validées** : aucun taux fabriqué, le cabinet les saisit
et les valide.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_REF_DIR = Path(__file__).parent / "ref"
BASE_DEVISE = "XAF"
_MONEY = Decimal("0.01")


class FxRateNotValidated(RuntimeError):
    """Un taux requis pour la conversion est absent ou non validé."""

    def __init__(self, devise: str) -> None:
        super().__init__(f"Taux de change non validé pour {devise!r} — conversion refusée.")
        self.devise = devise


class FxRate(BaseModel):
    """Un taux : valeur d'**une unité** de ``devise`` exprimée en XAF."""

    devise: str
    taux_vers_xaf: Decimal | None = None
    validated: bool = False
    source: str = ""


def load_fx_seed(country: str = "cg") -> dict[str, Any]:
    """Charge la graine des taux depuis `ref/fx_rates_<country>.json`."""
    path = _REF_DIR / f"fx_rates_{country}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Table de taux introuvable pour {country!r} : {path}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def effective_rates(seed: Mapping[str, Any], overrides: Mapping[str, FxRate]) -> dict[str, FxRate]:
    """Fusionne graine + overrides tenant. XAF est toujours l'identité validée.

    Un override tenant (saisi et gouverné par le cabinet) prévaut sur la graine
    pour la devise concernée.
    """
    out: dict[str, FxRate] = {
        BASE_DEVISE: FxRate(
            devise=BASE_DEVISE,
            taux_vers_xaf=Decimal("1"),
            validated=True,
            source="Devise de référence",
        )
    }
    for code, entry in (seed.get("rates") or {}).items():
        devise = code.upper()
        taux = entry.get("taux_vers_xaf")
        out[devise] = FxRate(
            devise=devise,
            taux_vers_xaf=Decimal(str(taux)) if taux is not None else None,
            validated=bool(entry.get("validated", False)),
            source=str(entry.get("source", "")),
        )
    for devise, rate in overrides.items():
        out[devise.upper()] = rate
    return out


def _taux_valide(devise: str, rates: Mapping[str, FxRate]) -> Decimal:
    rate = rates.get(devise.upper())
    if rate is None or not rate.validated or rate.taux_vers_xaf is None:
        raise FxRateNotValidated(devise.upper())
    return rate.taux_vers_xaf


def convertir(
    montant: Decimal,
    de: str,
    vers: str,
    rates: Mapping[str, FxRate],
    *,
    quantize: Decimal = _MONEY,
) -> Decimal:
    """Convertit ``montant`` de la devise ``de`` vers la devise ``vers``.

    Déterministe : ``montant_xaf = montant × taux(de)`` puis
    ``résultat = montant_xaf ÷ taux(vers)``. S'abstient (`FxRateNotValidated`)
    si un taux requis n'est pas validé. XAF ↔ XAF est l'identité.
    """
    de_u, vers_u = de.upper(), vers.upper()
    if de_u == vers_u:
        return montant.quantize(quantize, rounding=ROUND_HALF_UP)
    taux_de = _taux_valide(de_u, rates)
    taux_vers = _taux_valide(vers_u, rates)
    montant_xaf = montant * taux_de
    resultat = montant_xaf / taux_vers
    return resultat.quantize(quantize, rounding=ROUND_HALF_UP)
