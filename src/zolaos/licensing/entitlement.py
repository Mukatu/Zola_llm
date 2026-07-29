"""Entitlement — droits de modules signés par Polaris (licence commerciale).

PROBLÈME RÉSOLU : la distribution des modules doit être décidée par le VENDEUR
(Polaris), pas paramétrable par le client sur sa box. Avant, `modules_actifs`
était (1) purement cosmétique (les endpoints restaient ouverts), (2) éditable par
le client (`PUT /v1/config`), (3) non persisté, (4) hors de tout contrôle vendeur.

Ici, un entitlement est un **grant SIGNÉ en RS256 (asymétrique)** : Polaris signe
avec sa clé PRIVÉE, la box vérifie avec la clé PUBLIQUE — la box ne peut ni
forger ni élever ses droits (prouvé : une clé publique ne peut pas signer).

**Modèle économique HYBRIDE** : un `tier` de base (bundle) + des `modules`
optionnels à la carte par-dessus. `effective_modules()` = modules du tier ∪ options,
borné au catalogue.

**Application** : au MONTAGE (`main.py`, profil box) — un module non couvert n'est
même pas monté (404), pas juste masqué. Enforcement **OPT-IN**
(`Settings.ENTITLEMENT_ENFORCED`, défaut False) pour ne pas casser dev/tests ; en
prod on l'active + on fournit la clé publique + la licence (fichier et/ou tunnel).
"""

from __future__ import annotations

from datetime import UTC, datetime

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from pydantic import BaseModel, Field

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.licensing.entitlement")

_ALGO = "RS256"  # asymétrique : la box (clé publique) ne peut pas forger
_ISSUER = "polaris"

# --- Catalogue des modules vendables (unités d'entitlement) -----------------
# Chaque module regroupe un ou plusieurs routers box (cf. le mapping de montage
# dans `api/main.py`). C'est l'unité que Polaris vend/accorde.
MODULES: frozenset[str] = frozenset(
    {"erp", "sirh", "bi", "crm", "marketing", "fintech", "cyber", "grc", "code"}
)

# --- Tiers (bundles) → modules de base inclus -------------------------------
TIERS: dict[str, frozenset[str]] = {
    "starter": frozenset({"erp"}),
    "business": frozenset({"erp", "sirh", "bi", "crm", "marketing"}),
    "full": MODULES,
}


class EntitlementError(Exception):
    """Erreur d'entitlement (base)."""


class EntitlementInvalid(EntitlementError):
    """Signature, émetteur ou claims invalides."""


class EntitlementExpired(EntitlementError):
    """Entitlement expiré."""


class Entitlement(BaseModel):
    """Droits de modules d'un tenant, tels qu'accordés par Polaris."""

    tenant_id: str
    tier: str
    modules: list[str] = Field(default_factory=list)  # à-la-carte, EN PLUS du tier
    license_id: str
    issued_at: datetime
    expires_at: datetime

    def effective_modules(self) -> frozenset[str]:
        """Modules réellement autorisés = tier ∪ options, borné au catalogue.

        Un tier inconnu → aucun module de base (dégradation sûre) ; une option
        hors catalogue est ignorée (jamais d'élévation par un module fantôme)."""
        base = TIERS.get(self.tier, frozenset())
        return frozenset(base | set(self.modules)) & MODULES

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


def sign_entitlement(ent: Entitlement, *, private_key_pem: str) -> str:
    """Signe un entitlement — côté ÉMETTEUR (Polaris/cortex). La clé PRIVÉE ne
    doit JAMAIS se trouver sur une box."""
    claims = {
        "iss": _ISSUER,
        "sub": ent.tenant_id,
        "tier": ent.tier,
        "modules": ent.modules,
        "jti": ent.license_id,
        "iat": int(ent.issued_at.timestamp()),
        "exp": int(ent.expires_at.timestamp()),
    }
    return jwt.encode(claims, private_key_pem, algorithm=_ALGO)


def verify_entitlement(token: str, *, public_key_pem: str) -> Entitlement:
    """Vérifie un entitlement — côté BOX (clé PUBLIQUE). Lève `EntitlementExpired`
    si expiré, `EntitlementInvalid` si signature/émetteur/claims invalides."""
    try:
        claims = jwt.decode(token, public_key_pem, algorithms=[_ALGO], issuer=_ISSUER)
    except ExpiredSignatureError as exc:
        raise EntitlementExpired(str(exc)) from exc
    except JWTError as exc:
        raise EntitlementInvalid(f"signature/émetteur invalides: {exc}") from exc
    try:
        return Entitlement(
            tenant_id=claims["sub"],
            tier=claims["tier"],
            modules=list(claims.get("modules", [])),
            license_id=claims["jti"],
            issued_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
            expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise EntitlementInvalid(f"claims incomplets: {exc}") from exc


def load_box_entitlement(settings) -> Entitlement | None:  # type: ignore[no-untyped-def]
    """Charge l'entitlement de CETTE box : jeton inline (`ENTITLEMENT_LICENSE_JWT`)
    ou fichier (`ENTITLEMENT_LICENSE_FILE`), vérifié avec `ENTITLEMENT_PUBLIC_KEY`.

    Retourne `None` si absent/invalide/expiré (l'appelant décide du fail-closed
    selon `ENTITLEMENT_ENFORCED`). Ne lève jamais : une licence illisible ne doit
    pas planter le démarrage, elle doit couper les modules (via resolve_box_modules)."""
    pub = settings.ENTITLEMENT_PUBLIC_KEY.get_secret_value()
    if not pub:
        _log.warning("entitlement.no_public_key")
        return None
    token = settings.ENTITLEMENT_LICENSE_JWT.get_secret_value().strip()
    if not token and settings.ENTITLEMENT_LICENSE_FILE:
        try:
            from pathlib import Path

            token = Path(settings.ENTITLEMENT_LICENSE_FILE).read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.error("entitlement.file_unreadable", error=str(exc))
            return None
    if not token:
        _log.warning("entitlement.no_license")
        return None
    try:
        return verify_entitlement(token, public_key_pem=pub)
    except EntitlementError as exc:
        _log.error("entitlement.invalid", error=str(exc))
        return None


def resolve_box_modules(settings) -> frozenset[str] | None:  # type: ignore[no-untyped-def]
    """Modules à monter pour cette box.

    - `None`  → enforcement DÉSACTIVÉ (`ENTITLEMENT_ENFORCED=False`, défaut) :
      monter TOUS les modules (comportement dev/actuel, tests inchangés).
    - `frozenset` → enforcement ACTIF : monter uniquement ces modules. Un
      entitlement absent/expiré donne `frozenset()` (**fail-closed** : rien),
      jamais un accès par défaut."""
    if not settings.ENTITLEMENT_ENFORCED:
        return None
    ent = load_box_entitlement(settings)
    if ent is None or ent.is_expired():
        _log.error("entitlement.enforced_but_missing_or_expired — fail-closed (aucun module)")
        return frozenset()
    modules = ent.effective_modules()
    _log.info("entitlement.resolved", tenant=ent.tenant_id, tier=ent.tier, modules=sorted(modules))
    return modules
