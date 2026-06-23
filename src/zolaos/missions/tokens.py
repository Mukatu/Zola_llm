"""Émission et vérification des JWT mission (Polaris-7+8).

Un JWT mission est émis quand un consultant Polaris démarre une mission d'audit
chez une entreprise cliente. Il porte :

  - `sub`       : id du consultant (UUID utilisateur cabinet)
  - `mid`       : id de la mission (UUID, claim métier)
  - `cab`       : id du tenant cabinet (Polaris)
  - `cli`       : id du tenant client
  - `off`       : nom de l'offre Polaris (`conformite_rh`, `fiscal_ohada`, …)
  - `scope`     : liste de tags RBAC autorisés (ex: ["country:cg", "module:travail_cg"])
  - `iat`/`exp` : standard JWT

Vérification triple :
  1. Signature HS256 (clé `Settings.JWT_SECRET`)
  2. Mission EXISTE en DB et `status='active'`
  3. `expires_at > now()` (DB l'a aussi en CHECK constraint, on re-vérifie côté token)

L'expiration est portée par le token (claim `exp`) ET par la mission DB
(`expires_at`). En cas de divergence, le minimum des deux fait foi. Une mission
révoquée (`revoked_at IS NOT NULL`) bloque immédiatement même si le JWT est
encore dans sa fenêtre.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings
from zolaos.db.models import Mission

_log = get_logger("zolaos.missions.tokens")

_ALGORITHM = "HS256"
_DEFAULT_TTL = timedelta(hours=2)
_MAX_TTL = timedelta(hours=6)  # plafond dur


# =============================================================================
# Modèles
# =============================================================================


@dataclass(frozen=True)
class MissionClaims:
    """Claims décodés d'un JWT mission, après vérification signature + DB."""

    consultant_user_id: uuid.UUID
    mission_id: uuid.UUID
    cabinet_tenant_id: uuid.UUID
    client_tenant_id: uuid.UUID
    offre: str
    scope_tags: list[str]
    issued_at: datetime
    expires_at: datetime


class MissionTokenError(Exception):
    """Token invalide, expiré, ou mission révoquée / inconnue."""


# =============================================================================
# Émission
# =============================================================================


def issue_mission_token(
    *,
    mission: Mission,
    settings: Settings,
    ttl: timedelta | None = None,
) -> tuple[str, datetime]:
    """Émet un JWT mission à partir d'un objet `Mission` chargé depuis la DB.

    Retourne (token, expires_at_effectif). Le TTL effectif est le min entre
    le TTL demandé (ou défaut), le plafond `_MAX_TTL`, et `mission.expires_at - now()`.
    Lève ValueError si la mission n'est pas `active` ou déjà expirée en DB.
    """
    if mission.status != "active":
        raise ValueError(f"Mission {mission.id} non active (statut={mission.status})")
    now = datetime.now(UTC)
    db_remaining = mission.expires_at - now
    if db_remaining <= timedelta(0):
        raise ValueError(f"Mission {mission.id} déjà expirée en DB ({mission.expires_at})")

    requested = ttl or _DEFAULT_TTL
    effective_ttl = min(requested, _MAX_TTL, db_remaining)
    exp_dt = now + effective_ttl

    payload = {
        "sub": str(mission.consultant_user_id),
        "mid": str(mission.id),
        "cab": str(mission.cabinet_tenant_id),
        "cli": str(mission.client_tenant_id),
        "off": mission.offre,
        "scope": list(mission.scope_tags or []),
        "iat": int(now.timestamp()),
        "exp": int(exp_dt.timestamp()),
    }
    secret = settings.JWT_SECRET.get_secret_value()
    if not secret:
        raise ValueError("JWT_SECRET non configuré, impossible d'émettre un token mission")
    token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
    _log.info(
        "mission.token.issued",
        mission_id=str(mission.id),
        consultant=str(mission.consultant_user_id),
        client=str(mission.client_tenant_id),
        ttl_seconds=int(effective_ttl.total_seconds()),
    )
    return token, exp_dt


# =============================================================================
# Vérification
# =============================================================================


async def verify_mission_token(
    token: str,
    *,
    session: AsyncSession,
    settings: Settings,
) -> MissionClaims:
    """Vérifie la signature, charge la mission, valide statut + expiration.

    Lève `MissionTokenError` si :
    - signature invalide / format malformé
    - claim manquant
    - mission introuvable en DB
    - mission non active (revoked/expired/completed)
    - mission expirée côté DB (peut différer du `exp` JWT)
    """
    secret = settings.JWT_SECRET.get_secret_value()
    if not secret:
        raise MissionTokenError("JWT_SECRET non configuré")
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise MissionTokenError(f"JWT invalide : {exc}") from exc

    try:
        mission_id = uuid.UUID(payload["mid"])
    except (KeyError, ValueError) as exc:
        raise MissionTokenError(f"claim 'mid' manquant ou invalide : {exc}") from exc

    mission = await session.scalar(select(Mission).where(Mission.id == mission_id))
    if mission is None:
        raise MissionTokenError(f"mission {mission_id} introuvable en DB")
    if mission.status != "active":
        raise MissionTokenError(f"mission {mission_id} non active (statut={mission.status})")
    now = datetime.now(UTC)
    if mission.expires_at <= now:
        # Marquer expired implicitement côté logique (la DB peut être mise à jour
        # par un job batch ; ici on bloque juste l'accès).
        raise MissionTokenError(f"mission {mission_id} expirée à {mission.expires_at}")
    if mission.revoked_at is not None:
        raise MissionTokenError(f"mission {mission_id} révoquée à {mission.revoked_at}")

    try:
        claims = MissionClaims(
            consultant_user_id=uuid.UUID(payload["sub"]),
            mission_id=mission_id,
            cabinet_tenant_id=uuid.UUID(payload["cab"]),
            client_tenant_id=uuid.UUID(payload["cli"]),
            offre=payload["off"],
            scope_tags=list(payload.get("scope") or []),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (KeyError, ValueError) as exc:
        raise MissionTokenError(f"claims malformés : {exc}") from exc

    _log.info(
        "mission.token.verified",
        mission_id=str(mission_id),
        consultant=str(claims.consultant_user_id),
        client=str(claims.client_tenant_id),
        scope=claims.scope_tags,
    )
    return claims
