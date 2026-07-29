"""Licence commerciale / entitlement de modules (distribution pilotée par Polaris).

L'entitlement décide QUELS modules une box a le droit d'exposer. Il est **signé
par Polaris** (le vendeur) et seulement **vérifié** par la box — jamais éditable
côté client. Cf. `entitlement.py` et `docs/LICENSING.md`.
"""

from zolaos.licensing.entitlement import (
    MODULES,
    TIERS,
    Entitlement,
    EntitlementError,
    EntitlementExpired,
    EntitlementInvalid,
    effective_modules_for,
    load_box_entitlement,
    resolve_box_modules,
    sign_entitlement,
    verify_entitlement,
)

__all__ = [
    "MODULES",
    "TIERS",
    "Entitlement",
    "EntitlementError",
    "EntitlementExpired",
    "EntitlementInvalid",
    "effective_modules_for",
    "load_box_entitlement",
    "resolve_box_modules",
    "sign_entitlement",
    "verify_entitlement",
]
