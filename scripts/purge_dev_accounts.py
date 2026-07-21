"""Purge les comptes jetables créés par l'auto-login de développement.

Le dev-token forge des comptes ``consultant-<hex>@polaris.cg`` (sans mot de passe
connu). Ils ne doivent pas subsister en production. Ce script les supprime — et
uniquement eux (motif strict). Les sessions/clés liées tombent en cascade (FK).

Sécurité : **dry-run par défaut** (liste seulement). Ajouter ``--yes`` pour exécuter.

Usage ::

    docker exec -it zolaos-app python scripts/purge_dev_accounts.py        # aperçu
    docker exec -it zolaos-app python scripts/purge_dev_accounts.py --yes  # suppression
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.settings import get_settings
from zolaos.db.models import User

# Motif strict des comptes forgés par dev-token. Ancré (^…$) pour ne jamais
# attraper un compte réel qui contiendrait « consultant ».
_DEV_PATTERN = r"^consultant-[0-9a-f]+@polaris\.cg$"


async def _run(execute: bool) -> None:
    settings = get_settings()
    dsn = settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(dsn, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            rows = (
                await session.execute(select(User.email).where(User.email.op("~")(_DEV_PATTERN)))
            ).scalars().all()
            print(f"Comptes de dev correspondant au motif : {len(rows)}")
            for email in rows:
                print(f"  - {email}")
            if not rows:
                return
            if not execute:
                print("\n(dry-run) Rien supprimé. Relancer avec --yes pour exécuter.")
                return
            await session.execute(delete(User).where(User.email.op("~")(_DEV_PATTERN)))
            await session.commit()
            print(f"\nSupprimé : {len(rows)} comptes.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge des comptes de dev (dev-token).")
    parser.add_argument("--yes", action="store_true", help="Exécute la suppression (sinon dry-run).")
    args = parser.parse_args()
    asyncio.run(_run(execute=args.yes))


if __name__ == "__main__":
    main()
