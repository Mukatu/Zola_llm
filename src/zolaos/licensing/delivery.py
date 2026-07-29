"""Livraison de la licence courante d'un tenant — côté CORTEX.

Utilisé par le canal de tunnel (`zolaos.tunnel.channel`) pour répondre au
`license_pull` d'une box : on résout l'état de licence du tenant depuis
`core.license_grants` et on renvoie (statut, jeton).

Séparé du router `cortex_entitlements` (qui porte les dépendances FastAPI) : ici,
c'est une simple requête DB réutilisable hors contexte HTTP. La box, elle, ne fait
que **vérifier** le jeton reçu avec la clé publique — cette table reste côté cortex.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from zolaos.core.logging import get_logger
from zolaos.db.models import LicenseGrant
from zolaos.db.session import get_session_factory

_log = get_logger("zolaos.licensing.delivery")

# Statuts renvoyés à la box. "active" porte un jeton ; les autres, non.
LICENSE_STATUS = ("active", "revoked", "expired", "none")


async def active_license_for_tenant(tenant_id: str) -> tuple[str, str | None]:
    """Résout l'état de licence courant d'un tenant → (statut, jeton).

    - ``active``  : licence vivante → jeton signé à livrer.
    - ``revoked`` : la plus récente a été révoquée → pas de jeton (la box retirera
      son fichier de licence → fail-closed au prochain redémarrage).
    - ``expired`` : la plus récente est expirée → idem.
    - ``none``    : aucune licence pour ce tenant → no-op côté box.

    Le renouvellement révoquant les antérieures, la licence « la plus récente »
    (par ``created_at``) porte l'état courant. Ouvre sa propre session (appelé hors
    contexte de requête, depuis la boucle du tunnel)."""
    try:
        tuuid = uuid.UUID(tenant_id)
    except ValueError:
        return ("none", None)

    async with get_session_factory()() as session:
        grant = (
            await session.execute(
                select(LicenseGrant)
                .where(LicenseGrant.tenant_id == tuuid)
                .order_by(LicenseGrant.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if grant is None:
        return ("none", None)
    if grant.revoked_at is not None:
        return ("revoked", None)
    if datetime.now(UTC) >= grant.expires_at:
        return ("expired", None)
    return ("active", grant.token)
