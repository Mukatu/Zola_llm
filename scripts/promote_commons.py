#!/usr/bin/env python
"""Promotion des candidats validés du communs → ``rag_commons`` (opération admin).

**Rôle migrator** (écriture `rag_commons` + mise à jour du statut + journal
d'audit) : la promotion est hors chemin applicatif (l'app n'a que le SELECT sur
`rag_commons`, zero-trust). Le premier appel charge le modèle d'embeddings bge-m3.

    python scripts/promote_commons.py [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.commons.promotion import promote_validated
from zolaos.core.settings import get_settings
from zolaos.db.store_models import ContribCandidate


async def main(limit: int, dry_run: bool) -> None:
    settings = get_settings()
    dsn = settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(dsn, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            n = (
                await session.execute(
                    select(func.count())
                    .select_from(ContribCandidate)
                    .where(ContribCandidate.status == "validated")
                )
            ).scalar_one()
            print(f"Candidats validés à promouvoir : {n} (dry_run={dry_run}).")
            if dry_run or not n:
                return
            res = await promote_validated(session, limit=limit)
            await session.commit()
            print(f"Terminé : {res}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Promotion communs → rag_commons (admin)")
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--dry-run", action="store_true", help="compter sans écrire")
    args = p.parse_args()
    asyncio.run(main(args.limit, args.dry_run))
