"""Crée (ou met à jour) un compte utilisateur avec mot de passe — amorçage prod.

Le login de production (``POST /v1/auth/login``) vérifie email + mot de passe.
Aucun compte n'a de mot de passe *connu* au départ (le dev-token forge des
comptes jetables) : ce script pose le premier admin réel.

Usage (dans le conteneur applicatif) ::

    docker exec -it zolaos-app python scripts/create_admin.py \
        --email admin@polaris.cg --display-name "Admin Polaris"

Le mot de passe est demandé de façon interactive (masqué) ou lu dans la variable
d'environnement ``ADMIN_PASSWORD``. Il n'est jamais journalisé ni stocké en clair
(hash bcrypt uniquement). Rejouer le script sur un email existant met à jour le
mot de passe (réinitialisation).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.rbac import ROLES, is_valid_role
from zolaos.core.security import hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import User


async def _upsert(
    *,
    email: str,
    display_name: str,
    password: str,
    tenant_id: str | None,
    country: str,
    role: str,
) -> str:
    settings = get_settings()
    dsn = settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(dsn, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            pwd_hash = hash_password(password)
            if user is None:
                user = User(
                    email=email,
                    display_name=display_name,
                    password_hash=pwd_hash,
                    is_active=True,
                    country=country,
                    tenant_id=tenant_id,
                    role=role,
                )
                session.add(user)
                action = "créé"
            else:
                user.password_hash = pwd_hash
                user.display_name = display_name
                user.is_active = True
                user.role = role
                if tenant_id is not None:
                    user.tenant_id = tenant_id
                action = "mis à jour"
            await session.commit()
            return action
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Amorçage d'un compte admin ZolaOS.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", default="Administrateur")
    parser.add_argument("--tenant-id", default=None, help="Tag tenant (cloisonnement corpus privé).")
    parser.add_argument("--country", default="cg")
    parser.add_argument(
        "--role",
        default="admin",
        help=f"Rôle RBAC ({' | '.join(ROLES)}). Défaut : admin.",
    )
    args = parser.parse_args()

    if not is_valid_role(args.role):
        sys.exit(f"Refusé : rôle invalide '{args.role}'. Attendu : {', '.join(ROLES)}.")

    email = args.email.strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Mot de passe : ")
    if len(password) < 10:
        sys.exit("Refusé : le mot de passe doit faire au moins 10 caractères.")

    action = asyncio.run(
        _upsert(
            email=email,
            display_name=args.display_name,
            password=password,
            tenant_id=args.tenant_id,
            country=args.country,
            role=args.role,
        )
    )
    print(f"Compte {email} ({args.role}) {action}.")


if __name__ == "__main__":
    main()
