"""Purge les tenants (et leurs missions) créés par la suite de tests.

Ces artefacts (``client-test-<hex>``, ``polaris-test-<hex>``, ``other-cab-*``,
``client-A/B-*``) polluent l'annuaire Clients du cockpit. Ce script les supprime —
et uniquement eux (motif strict, ancré). Les tenants réels sont préservés.

Ordre : d'abord les missions qui les référencent (FK RESTRICT), puis les tenants.

Sécurité : **dry-run par défaut**. Ajouter ``--yes`` pour exécuter.

Usage ::

    docker exec -it zolaos-app python scripts/purge_test_tenants.py        # aperçu
    docker exec -it zolaos-app python scripts/purge_test_tenants.py --yes  # suppression
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.settings import get_settings

# Motif strict des tenants de test. Ancré pour ne jamais attraper un tenant réel.
_PATTERN = r"^(client-test|polaris-test|other-cab|client-[AB])-"


async def _run(execute: bool) -> None:
    settings = get_settings()
    dsn = settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(dsn, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            tenants = (
                await session.execute(
                    text("SELECT count(*) FROM core.tenants WHERE name ~ :p"), {"p": _PATTERN}
                )
            ).scalar_one()
            missions = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM core.missions m JOIN core.tenants t "
                        "ON (t.id = m.client_tenant_id OR t.id = m.cabinet_tenant_id) "
                        "WHERE t.name ~ :p"
                    ),
                    {"p": _PATTERN},
                )
            ).scalar_one()
            print(f"Tenants de test : {tenants} | missions liées : {missions}")
            if not tenants:
                return
            if not execute:
                print("\n(dry-run) Rien supprimé. Relancer avec --yes pour exécuter.")
                return

            # 1) missions référençant un tenant de test (contrainte FK RESTRICT).
            await session.execute(
                text(
                    "DELETE FROM core.missions m USING core.tenants t "
                    "WHERE (t.id = m.client_tenant_id OR t.id = m.cabinet_tenant_id) "
                    "AND t.name ~ :p"
                ),
                {"p": _PATTERN},
            )
            # 2) les tenants de test.
            await session.execute(
                text("DELETE FROM core.tenants WHERE name ~ :p"), {"p": _PATTERN}
            )
            await session.commit()
            print(f"\nSupprimé : {missions} missions + {tenants} tenants.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge des tenants de test.")
    parser.add_argument("--yes", action="store_true", help="Exécute la suppression (sinon dry-run).")
    args = parser.parse_args()
    asyncio.run(_run(execute=args.yes))


if __name__ == "__main__":
    main()
