"""Configuration de la journalisation structurée (structlog).

Format JSON en prod/staging, console lisible en dev. Tous les logs incluent
service, env, country par défaut.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from zolaos.core.settings import Settings

# Champs sensibles automatiquement masqués dans les logs.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "api_key",
        "anthropic_api_key",
        "jwt_secret",
        "encryption_key_audit",
        "api_key_pepper",
        "authorization",
        "cookie",
        "set-cookie",
    }
)


def _redact_sensitive(_logger: Any, _name: str, event_dict: EventDict) -> EventDict:
    """Remplace toute valeur dont la clé matche un nom sensible par '***'."""
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "***"
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure structlog et le logger Python standard."""

    level = getattr(logging, settings.LOG_LEVEL)

    # Stdlib logger : tout passe par structlog ensuite.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redact_sensitive,
    ]

    if settings.LOG_FORMAT == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Contexte global injecté dans chaque log.
    structlog.contextvars.bind_contextvars(
        service=settings.OTEL_SERVICE_NAME,
        env=settings.APP_ENV,
        country=settings.DEFAULT_COUNTRY,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Helper pour récupérer un logger structuré."""
    return structlog.get_logger(name)
