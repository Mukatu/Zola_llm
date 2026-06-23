"""Point d'entrée FastAPI de ZolaOS.

Phase 0 : squelette + observabilité + endpoints minimaux (/health, /metrics).
Les routes métier (/v1/query, /v1/agents) arrivent en Phase 1.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from zolaos import __version__
from zolaos.api.v1.routes import router as v1_router
from zolaos.core.logging import configure_logging, get_logger
from zolaos.core.metrics import (
    EXTERNAL_FALLBACK_ENABLED,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from zolaos.core.rate_limit import RedisRateLimiter, make_redis_client
from zolaos.core.settings import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    settings = get_settings()
    configure_logging(settings)
    log = get_logger("zolaos.startup")

    EXTERNAL_FALLBACK_ENABLED.set(1 if settings.ENABLE_EXTERNAL_FALLBACK else 0)

    log.info(
        "zolaos.startup",
        version=__version__,
        env=settings.APP_ENV,
        country=settings.DEFAULT_COUNTRY,
        external_fallback_enabled=settings.ENABLE_EXTERNAL_FALLBACK,
    )
    yield
    log.info("zolaos.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factory FastAPI. Exposée pour faciliter les tests."""
    settings = settings or get_settings()

    app = FastAPI(
        title="ZolaOS",
        description="Plateforme IA multi-agents souveraine — République du Congo",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_prod else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    rate_limiter: RedisRateLimiter | None = None
    if not settings.is_prod or settings.APP_ENV == "staging" or settings.APP_ENV == "prod":
        # En dev, on initialise quand même : Redis tourne déjà dans le compose.
        try:
            rate_limiter = RedisRateLimiter(
                redis_client=make_redis_client(settings),
                per_minute=settings.RATE_LIMIT_PER_MINUTE,
            )
        except Exception:  # noqa: BLE001
            rate_limiter = None  # Redis indispo : on dégrade sans bloquer.

    @app.middleware("http")
    async def request_pipeline(request: Request, call_next: Any) -> Response:
        # 1. Rate limiting (skip /health, /metrics, /docs, /openapi.json).
        path_raw = request.url.path
        skip_rl = path_raw in {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}
        if rate_limiter is not None and not skip_rl:
            identifier = (
                request.headers.get("X-API-Key")
                or request.headers.get("Authorization", "")
                or (request.client.host if request.client else "anonymous")
            )
            rl = await rate_limiter.check(identifier)
            if not rl.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate_limit_exceeded",
                    headers={
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(rl.reset_seconds),
                    },
                )

        # 2. Metrics
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(elapsed)
        return response

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, Any]:
        """Liveness probe."""
        return {
            "status": "ok",
            "version": __version__,
            "env": settings.APP_ENV,
            "country": settings.DEFAULT_COUNTRY,
            "external_fallback_enabled": settings.ENABLE_EXTERNAL_FALLBACK,
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Expose les métriques au format Prometheus."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(v1_router)

    # Configuration / personnalisation : montée dans les deux profils.
    # box → config client personnalisée ; cortex → config consultant uniforme.
    from zolaos.api.v1.config import router as config_router

    app.include_router(config_router)

    # Routes Zolabox (Polaris-8) : exposées uniquement en profil `box`. En
    # profil `cortex`, le router n'est pas monté → 404 sur /v1/box/* (préférable
    # à un 500 ProfileError qui révélerait l'existence des routes).
    if settings.ZOLAOS_PROFILE == "box":
        from zolaos.api.v1.bi import router as bi_router
        from zolaos.api.v1.box import router as box_router
        from zolaos.api.v1.crm import router as crm_router
        from zolaos.api.v1.erp import router as erp_router
        from zolaos.api.v1.mkt import router as mkt_router

        app.include_router(box_router)
        # Moteurs déterministes (ERP/ops, CRM, BI, Marketing) exposés au frontend client.
        app.include_router(erp_router)
        app.include_router(crm_router)
        app.include_router(bi_router)
        app.include_router(mkt_router)

    # Routes Zolacortex (gestion missions) : exposées uniquement en profil `cortex`.
    # Inversement, en profil `box`, 404 sur /v1/cortex/*.
    if settings.ZOLAOS_PROFILE == "cortex":
        from zolaos.api.v1.cortex import router as cortex_router

        app.include_router(cortex_router)

    return app


app = create_app()
