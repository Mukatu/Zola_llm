"""Configuration Alembic — utilise le DSN migrations construit depuis Settings."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from zolaos.core.settings import get_settings
from zolaos.db.base import Base
from zolaos.db import models  # noqa: F401  (charge les modèles dans le metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injecte le DSN dynamiquement (depuis .env via Settings) plutôt que dans alembic.ini.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.postgres_dsn_migrations)

# Les schémas (core, memory, rag_*, audit) sont créés par
# `infra/postgres/01_init_schemas.sql` au bootstrap du conteneur.
# Alembic gère uniquement les tables à l'intérieur de ces schémas.
target_metadata = Base.metadata


def include_object(obj: object, name: str | None, type_: str, *_args: object) -> bool:
    """Filtre : on ne touche jamais aux schémas eux-mêmes (gérés par le bootstrap)."""
    if type_ == "schema":
        return False
    _ = obj, name
    return True


def run_migrations_offline() -> None:
    """Exécution offline (génération de SQL sans connexion)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
        version_table_schema="core",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Exécution online (connexion réelle à Postgres)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table_schema="core",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
