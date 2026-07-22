"""Semence de développement HYBRIDE (idempotent).

Prépare l'atelier pour développer la chaîne box ⇄ cortex sans montage manuel :
- un admin (login réel, l'atelier tourne en staging → pas d'auto-login) ;
- un tenant cabinet + un tenant client, l'admin rattaché au cabinet ;
- un credential de box pour le client (+ box_url vers la box locale).

Imprime sur stdout, en clé=valeur, ce que `dev_up.ps1` injecte dans `.env` pour
que l'agent de tunnel de la box se connecte :

    BOX_TENANT_ID=<uuid client>
    BOX_CREDENTIAL=<zbx_…>

Rejouer rote le credential (l'atelier récupère toujours un credential valide).
"""

from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.rbac import ROLE_ADMIN
from zolaos.core.security import generate_box_credential, hash_password
from zolaos.core.settings import get_settings
from zolaos.db.models import Tenant, User

_CABINET_NAME = "Polaris (dev)"
_CLIENT_NAME = "Client Dev"
_BOX_URL = "http://zolaos-app:8000"  # la box, joignable depuis le cortex (réseau docker)


async def _get_or_create_tenant(session, name: str, tenant_type: str) -> Tenant:
    t = (await session.execute(select(Tenant).where(Tenant.name == name))).scalar_one_or_none()
    if t is None:
        t = Tenant(name=name, tenant_type=tenant_type, country="cg", is_active=True)
        session.add(t)
        await session.flush()
    return t


async def _run(admin_email: str, admin_password: str) -> None:
    settings = get_settings()
    dsn = settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(dsn, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            cabinet = await _get_or_create_tenant(session, _CABINET_NAME, "cabinet")
            client = await _get_or_create_tenant(session, _CLIENT_NAME, "client")

            # Admin (rattaché au cabinet ; le rattachement est requis pour les missions).
            admin = (
                await session.execute(select(User).where(User.email == admin_email))
            ).scalar_one_or_none()
            if admin is None:
                admin = User(
                    email=admin_email,
                    display_name="Admin Dev",
                    password_hash=hash_password(admin_password),
                    is_active=True,
                    role=ROLE_ADMIN,
                    tenant_id="polaris",
                )
                session.add(admin)
            else:
                admin.password_hash = hash_password(admin_password)
                admin.role = ROLE_ADMIN
            admin.tenant_uuid = cabinet.id

            # Credential de box pour le client (roté à chaque semence).
            pepper = settings.API_KEY_PEPPER.get_secret_value()
            plain, prefix, cred_hash = generate_box_credential(pepper=pepper)
            client.box_credential_hash = cred_hash
            client.box_credential_prefix = prefix
            client.box_url = _BOX_URL

            await session.commit()

            # Sortie machine pour dev_up.
            print(f"BOX_TENANT_ID={client.id}")
            print(f"BOX_CREDENTIAL={plain}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Semence de dev hybride (idempotent).")
    parser.add_argument("--admin-email", default=os.environ.get("DEV_ADMIN_EMAIL", "admin@polaris.cg"))
    parser.add_argument("--admin-password", default=os.environ.get("DEV_ADMIN_PASSWORD", "Dev-Local-2026!"))
    args = parser.parse_args()
    asyncio.run(_run(args.admin_email, args.admin_password))


if __name__ == "__main__":
    main()
