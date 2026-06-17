"""Gestion des sessions async SQLAlchemy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from zolaos.core.settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Engine asynchrone partagé (rôle applicatif)."""
    settings = get_settings()
    return create_async_engine(
        settings.postgres_dsn_app,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : injecte une session par requête."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


def reset_engine_cache(settings: Settings | None = None) -> None:
    """Utilitaire de test pour réinitialiser le cache d'engine."""
    _ = settings
    get_engine.cache_clear()
    get_session_factory.cache_clear()
