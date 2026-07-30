"""Point d'entrée FastAPI de ZolaOS.

Phase 0 : squelette + observabilité + endpoints minimaux (/health, /metrics).
Les routes métier (/v1/query, /v1/agents) arrivent en Phase 1.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
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

    # Agent de tunnel (profil box) : dial sortant persistant vers le Cortex, pour
    # que celui-ci atteigne cette Zolabox derrière son pare-feu (déploiement hybride).
    tunnel_task: asyncio.Task[None] | None = None
    if settings.ZOLAOS_PROFILE == "box" and settings.TUNNEL_CORTEX_URL:
        from zolaos.tunnel.agent import run_box_tunnel_agent

        # L'agent tourne dans CE process : on lui passe l'état d'entitlement pour
        # qu'un refresh de licence l'applique à chaud (révocation immédiate).
        ent_state = getattr(app.state, "entitlement_state", None)
        tunnel_task = asyncio.create_task(run_box_tunnel_agent(settings, ent_state))

    yield

    if tunnel_task is not None:
        tunnel_task.cancel()
        with suppress(asyncio.CancelledError):
            await tunnel_task
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
        except Exception:
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

        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
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

    # Cœur moteur (souverain, générique) : /v1/query, /v1/query/stream,
    # /v1/agents. Monté dans TOUS les profils (y compris `engine` headless).
    app.include_router(v1_router)

    # Adaptateur OpenAI-compatible (/v1/chat/completions) : drop-in pour outils
    # tiers. Surface MOTEUR → tous les profils. Auth + metering + quota par clé
    # via `require_quota` (comme /v1/query).
    from zolaos.api.v1.openai_compat import router as openai_compat_router
    from zolaos.core.metering import require_quota

    app.include_router(openai_compat_router, dependencies=[Depends(require_quota)])

    # Packs juridiction (multi-pays) : « ajouter un pays = ajouter un pack ».
    # Surface moteur (métadonnées), montée dans tous les profils.
    from zolaos.api.v1.jurisdictions import router as jurisdictions_router

    app.include_router(jurisdictions_router)

    # Authentification de production : login email + mot de passe, cookies
    # httpOnly + refresh + CSRF. Montée dans tous les environnements (le
    # moteur générique a besoin d'une identité, même en profil `engine`).
    from zolaos.api.v1.auth import router as auth_router

    app.include_router(auth_router)

    # Auto-login de développement (jeton local, 404 hors dev). Universel lui
    # aussi (comportement inchangé : le router s'auto-neutralise hors dev).
    from zolaos.api.v1.auth_dev import router as auth_dev_router

    app.include_router(auth_dev_router)

    # Ce qui suit est une préoccupation applicative box/cortex (config
    # personnalisée, feedback, bibliothèque documentaire, outils juridiques,
    # communs de connaissance) — PAS le moteur générique. Absent en profil
    # `engine` (headless).
    if settings.ZOLAOS_PROFILE in ("box", "cortex"):
        # Configuration / personnalisation : montée dans les deux profils.
        # box → config client personnalisée ; cortex → config consultant uniforme.
        from zolaos.api.v1.config import router as config_router

        app.include_router(config_router)

        # Feedback agents (transverse box + cortex) : capture du retour utilisateur
        # (verdict ✓/✗ + correction experte) — socle de l'auto-amélioration.
        from zolaos.api.v1.feedback import router as feedback_router

        app.include_router(feedback_router)

        # Bibliothèque documentaire (transverse) : consultation directe des corpus
        # RAG (Actes uniformes, conventions, CGI, LNME…), lecture seule.
        from zolaos.api.v1.kb import router as kb_router

        app.include_router(kb_router)

        # Pôle juridique — outils (traduction de contrats étrangers).
        from zolaos.api.v1.legal import router as legal_router

        app.include_router(legal_router)

        # Communs de connaissance (niveau 3) : consentement opt-in + extraction.
        from zolaos.api.v1.commons import router as commons_router

        app.include_router(commons_router)

    # Routes Zolabox (Polaris-8) : exposées uniquement en profil `box`. En
    # profil `cortex`, le router n'est pas monté → 404 sur /v1/box/* (préférable
    # à un 500 ProfileError qui révélerait l'existence des routes).
    if settings.ZOLAOS_PROFILE == "box":
        # Le plan de données de la box exige une identité authentifiée (401 sinon).
        # Appliqué au montage → protège d'un coup tous les endpoints métier.
        from zolaos.api.auth import require_box_auth, require_box_csrf
        from zolaos.api.v1.bi import router as bi_router
        from zolaos.api.v1.box import router as box_router
        from zolaos.api.v1.categorisation import router as categorisation_router
        from zolaos.api.v1.code import router as code_router
        from zolaos.api.v1.crm import router as crm_router
        from zolaos.api.v1.cyber import router as cyber_router
        from zolaos.api.v1.documents import router as documents_router
        from zolaos.api.v1.erp import router as erp_router
        from zolaos.api.v1.evaluation import router as evaluation_router
        from zolaos.api.v1.fintech import router as fintech_router
        from zolaos.api.v1.formation import router as formation_router
        from zolaos.api.v1.gpec import router as gpec_router
        from zolaos.api.v1.grc import router as grc_router
        from zolaos.api.v1.hr import router as hr_router
        from zolaos.api.v1.imports import router as imports_router
        from zolaos.api.v1.mkt import router as mkt_router
        from zolaos.api.v1.recrutement import router as recrutement_router
        from zolaos.api.v1.store import router as store_router

        _box_auth = [Depends(require_box_auth), Depends(require_box_csrf)]

        # Plan de mission (tunnel Zero Trust) : toujours monté — ce n'est pas un
        # module vendable, son accès est gouverné par le JWT de mission.
        app.include_router(box_router)

        # Statut & refresh de l'entitlement (observabilité + forçage à chaud) :
        # pas un module vendable, toujours monté sous les gardes du plan de données.
        from zolaos.api.v1.box_entitlement import router as box_entitlement_router

        app.include_router(box_entitlement_router, dependencies=_box_auth)

        # Distribution des modules DÉCIDÉE PAR POLARIS (entitlement signé) : un
        # module non couvert n'est même PAS monté (→ 404, absent de l'OpenAPI),
        # pas juste masqué. `allowed is None` = enforcement désactivé
        # (ENTITLEMENT_ENFORCED=False, défaut) → tous les modules montés.
        #
        # Application À CHAUD : l'état vivant est posé sur `app.state` et chaque
        # module monté porte en plus une garde runtime (`require_module`). Une
        # révocation (refresh tunnel) réduit l'état → le module passe en 404 sans
        # redémarrer. Au boot, l'état == le jeu monté → la garde est un no-op.
        from zolaos.api.entitlement_gate import require_module
        from zolaos.licensing import EntitlementState

        ent_state = EntitlementState.from_settings(settings)
        app.state.entitlement_state = ent_state
        entitled = ent_state.allowed

        def _mount_module(router, module):  # type: ignore[no-untyped-def]
            if entitled is None or module in entitled:
                app.include_router(
                    router, dependencies=[*_box_auth, Depends(require_module(module))]
                )

        # (router box, module vendable) — cf. catalogue `zolaos.licensing.MODULES`.
        for _router, _module in (
            (erp_router, "erp"),
            (categorisation_router, "erp"),
            (store_router, "erp"),
            (imports_router, "erp"),
            (documents_router, "erp"),
            (crm_router, "crm"),
            (bi_router, "bi"),
            (mkt_router, "marketing"),
            (hr_router, "sirh"),
            (gpec_router, "sirh"),
            (recrutement_router, "sirh"),
            (formation_router, "sirh"),
            (evaluation_router, "sirh"),
            (fintech_router, "fintech"),
            (cyber_router, "cyber"),
            (grc_router, "grc"),
            (code_router, "code"),
        ):
            _mount_module(_router, _module)

    # Routes Zolacortex (gestion missions) : exposées uniquement en profil `cortex`.
    # Inversement, en profil `box`, 404 sur /v1/cortex/*.
    if settings.ZOLAOS_PROFILE == "cortex":
        from zolaos.api.v1.cortex import router as cortex_router

        app.include_router(cortex_router)

        # Cockpit cabinet — gestion des comptes (réservé rôle admin).
        from zolaos.api.v1.cortex_accounts import router as cortex_accounts_router

        app.include_router(cortex_accounts_router)

        # Cockpit cabinet — annuaire des clients / tenants (réservé rôle admin).
        from zolaos.api.v1.cortex_clients import router as cortex_clients_router

        app.include_router(cortex_clients_router)

        # Cockpit cabinet — gestion des entitlements de modules (réservé rôle
        # admin). Émet/liste/révoque/livre les licences signées par tenant. Seul
        # endroit détenant la clé privée d'émission (jamais sur une box).
        from zolaos.api.v1.cortex_entitlements import router as cortex_entitlements_router

        app.include_router(cortex_entitlements_router)

        # Cockpit cabinet — supervision (fleet) : vue d'ensemble des boxes clientes
        # (connexion tunnel, licence + expiration, missions actives). Réservé admin.
        from zolaos.api.v1.cortex_fleet import router as cortex_fleet_router

        app.include_router(cortex_fleet_router)

        # Cockpit cabinet — journal d'audit (consultation append-only des actions
        # sensibles : licences, comptes, credentials box, missions). Réservé admin.
        from zolaos.api.v1.cortex_audit import router as cortex_audit_router

        app.include_router(cortex_audit_router)

        # Cockpit cabinet — usage & facturation par tenant (agrège le grand livre
        # d'usage durable + barème par tier). Réservé admin, lecture seule.
        from zolaos.api.v1.cortex_billing import router as cortex_billing_router

        app.include_router(cortex_billing_router)

        # Cockpit cabinet — PSA : feuilles de temps → économie de mission →
        # taux d'occupation (outillage cabinet). Saisie consultant, agrégats admin.
        from zolaos.api.v1.cortex_psa import router as cortex_psa_router

        app.include_router(cortex_psa_router)

        # Cockpit cabinet — facturation d'honoraires (aval du PSA) : factures depuis
        # les temps approuvés + échéancier/relances. Réservé admin, actes audités.
        from zolaos.api.v1.cortex_invoices import router as cortex_invoices_router

        app.include_router(cortex_invoices_router)

        # Cockpit cabinet — CRM / pipeline commercial (amont) : opportunités →
        # conversion en mission. Saisie consultant, synthèse & conversion admin.
        from zolaos.api.v1.cortex_pipeline import router as cortex_pipeline_router

        app.include_router(cortex_pipeline_router)

        # Point d'entrée du tunnel inverse : les Zolabox s'y connectent (sortant).
        from zolaos.api.v1.tunnel import router as tunnel_router

        app.include_router(tunnel_router)

    return app


app = create_app()
