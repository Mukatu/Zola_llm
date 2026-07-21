"""Contrôle d'accès par rôle (RBAC).

Trois rôles, alignés sur la topologie Polaris :

- ``admin``      : administration de la plateforme (gestion des comptes) +
                   curation du communs. Réservé à l'exploitant.
- ``consultant`` : personnel du cabinet Polaris — usage de l'assistant, missions,
                   et curation du communs (ce sont les experts qui valident).
- ``client``     : utilisateur d'un tenant client (sa Zolabox) — usage seul, aucun
                   droit privilégié.

Le login dérive les **scopes** du jeton à partir du rôle : le rôle est stocké,
les scopes en sont une projection (jamais l'inverse). Ajouter un endpoint
privilégié = créer un scope ici et l'attribuer aux rôles concernés.
"""

from __future__ import annotations

# Scopes (granularité d'autorisation portée par le JWT).
SCOPE_COMMONS_CURATE = "commons:curate"  # promouvoir du savoir dans le communs
SCOPE_ADMIN_USERS = "admin:users"  # créer / désactiver / réinitialiser des comptes

ROLE_ADMIN = "admin"
ROLE_CONSULTANT = "consultant"
ROLE_CLIENT = "client"

ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_CONSULTANT, ROLE_CLIENT)

# Rôle → scopes. `client` n'a aucun scope (authentification = requête, rien de plus).
_ROLE_SCOPES: dict[str, tuple[str, ...]] = {
    ROLE_ADMIN: (SCOPE_COMMONS_CURATE, SCOPE_ADMIN_USERS),
    ROLE_CONSULTANT: (SCOPE_COMMONS_CURATE,),
    ROLE_CLIENT: (),
}

DEFAULT_ROLE = ROLE_CONSULTANT


def scopes_for_role(role: str | None) -> list[str]:
    """Scopes attribués à un rôle. Rôle inconnu/absent ⇒ aucun scope (fail-safe)."""
    return list(_ROLE_SCOPES.get(role or "", ()))


def is_valid_role(role: str) -> bool:
    return role in _ROLE_SCOPES
