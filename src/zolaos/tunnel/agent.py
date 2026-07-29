"""Tunnel inverse Zolabox → Zolacortex — côté BOX (agent).

Tourne dans le processus de la Zolabox (démarré au lifespan si ``TUNNEL_CORTEX_URL``
est défini et profil ``box``). Ouvre une connexion WebSocket **sortante** vers le
Cortex, s'authentifie (secret partagé + identité de tenant), puis sert les requêtes
RAG poussées par le Cortex en les relayant à sa PROPRE API locale
``/v1/box/rag/search`` — ce qui préserve la vérification du jeton de mission,
l'intersection de scope et la journalisation d'audit côté box.

Aucun port entrant n'est ouvert côté client : c'est la box qui appelle.
"""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx
import websockets

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings

_log = get_logger("zolaos.tunnel.agent")


async def run_box_tunnel_agent(settings: Settings, entitlement_state: Any = None) -> None:
    """Boucle de vie de l'agent : connexion, service, reconnexion sur coupure.

    `entitlement_state` (optionnel) : l'`EntitlementState` de l'app. Fourni, un
    refresh de licence reçu par le tunnel est appliqué À CHAUD (les modules retirés
    passent en 404 sans redémarrer)."""
    url = settings.TUNNEL_CORTEX_URL
    tenant_id = settings.ZOLAOS_BOX_TENANT_ID
    credential = settings.ZOLAOS_BOX_CREDENTIAL.get_secret_value()
    if not url or not tenant_id or not credential:
        _log.warning("tunnel.agent.disabled", reason="config_incomplete")
        return

    local_base = f"http://localhost:{settings.APP_PORT}"
    backoff = settings.TUNNEL_RECONNECT_SECONDS

    # mTLS : sur wss://, présente le certificat client de la box s'il est configuré
    # (vérifié par le proxy du Cortex contre la CA Polaris). Sur ws:// (dev) : None.
    ssl_ctx: ssl.SSLContext | None = None
    if url.startswith("wss://"):
        ssl_ctx = ssl.create_default_context()
        if settings.TUNNEL_CLIENT_CERT_PATH and settings.TUNNEL_CLIENT_KEY_PATH:
            ssl_ctx.load_cert_chain(
                certfile=settings.TUNNEL_CLIENT_CERT_PATH, keyfile=settings.TUNNEL_CLIENT_KEY_PATH
            )

    while True:
        try:
            async with websockets.connect(url, ssl=ssl_ctx, max_size=8 * 1024 * 1024) as ws:
                await ws.send(
                    json.dumps({"type": "hello", "tenant_id": tenant_id, "credential": credential})
                )
                _log.info("tunnel.agent.connected", cortex=url, tenant_id=tenant_id)
                async with httpx.AsyncClient(
                    base_url=local_base, timeout=httpx.Timeout(30.0)
                ) as http:
                    # Rafraîchissement de licence : tire l'entitlement du Cortex en
                    # continu (initial immédiat + périodique). Tâche concurrente du
                    # service RAG, sur le MÊME WebSocket sortant.
                    refresher = asyncio.create_task(_refresh_loop(ws, settings))
                    try:
                        async for raw in ws:
                            await _handle_frame(ws, http, raw, settings, entitlement_state)
                    finally:
                        refresher.cancel()
                        with suppress(asyncio.CancelledError):
                            await refresher
        except asyncio.CancelledError:
            _log.info("tunnel.agent.stopped")
            raise
        except Exception as exc:  # coupure réseau, cortex indispo, etc.
            _log.warning("tunnel.agent.disconnected", error=str(exc))
            await asyncio.sleep(backoff)


async def _refresh_loop(ws: Any, settings: Settings) -> None:
    """Tire périodiquement la licence du Cortex (pull initial immédiat, puis boucle).

    Désactivé si l'intervalle est nul ou si aucun fichier cible n'est configuré
    (rien où écrire le jeton). Une coupure du WS termine la boucle ; la boucle
    externe de l'agent reconnecte et relance un refresh (donc re-pull immédiat)."""
    interval = settings.ENTITLEMENT_REFRESH_SECONDS
    if interval <= 0 or not settings.ENTITLEMENT_LICENSE_FILE:
        _log.info("tunnel.license_refresh.disabled")
        return
    while True:
        try:
            await ws.send(json.dumps({"type": "license_pull", "req_id": uuid.uuid4().hex}))
        except Exception:  # canal cassé : on rend la main, la reconnexion re-pull
            return
        await asyncio.sleep(interval)


def _apply_license(settings: Settings, status: str, token: str | None) -> None:
    """Applique une réponse `license` au fichier de licence local (écriture atomique).

    - ``active`` + jeton : écrit le jeton s'il a changé (le montage effectif des
      modules se met à jour au prochain (re)démarrage — enforcement au montage).
    - ``revoked`` / ``expired`` : retire le fichier → fail-closed au redémarrage.
    - ``none`` : no-op (ne jamais écraser un fichier existant sur un cas vide)."""
    path = settings.ENTITLEMENT_LICENSE_FILE
    if not path:
        return
    p = Path(path)
    try:
        if status == "active" and token:
            current = p.read_text(encoding="utf-8").strip() if p.exists() else None
            if current == token:
                return  # inchangé : pas de réécriture
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(token, encoding="utf-8")
            os.replace(tmp, p)  # remplacement atomique
            _log.info("tunnel.license_written", changed=True)
        elif status in ("revoked", "expired"):
            if p.exists():
                p.unlink()
                _log.warning("tunnel.license_removed", status=status)
    except OSError as exc:
        _log.error("tunnel.license_apply_failed", error=str(exc))


async def _handle_frame(
    ws: Any,
    http: httpx.AsyncClient,
    raw: str | bytes,
    settings: Settings,
    entitlement_state: Any = None,
) -> None:
    """Relaie une requête du Cortex vers l'API box locale, renvoie la réponse."""
    try:
        msg = json.loads(raw)
    except Exception:
        return
    # Réponse à un `license_pull` : applique la licence au fichier local, puis
    # RECALCULE l'état à chaud (une révocation prend effet sans redémarrer).
    if msg.get("type") == "license":
        _apply_license(settings, str(msg.get("status") or ""), msg.get("token"))
        if entitlement_state is not None and entitlement_state.refresh():
            _log.info("tunnel.entitlement_hot_applied")
        return
    if msg.get("type") != "rag_search":
        return
    rid = msg.get("req_id")
    try:
        r = await http.post(
            "/v1/box/rag/search",
            headers={"Authorization": f"Bearer {msg.get('mission_token', '')}"},
            json={
                "schema": msg.get("schema"),
                "query": msg.get("query"),
                "required_tags": msg.get("required_tags", []),
                "k": msg.get("k", 5),
            },
        )
        if r.status_code >= 400:
            await ws.send(
                json.dumps(
                    {
                        "type": "error",
                        "req_id": rid,
                        "detail": f"box_{r.status_code}: {r.text[:200]}",
                    }
                )
            )
            return
        data = r.json()
        await ws.send(
            json.dumps({"type": "rag_result", "req_id": rid, "matches": data.get("matches", [])})
        )
    except Exception as exc:
        await ws.send(
            json.dumps({"type": "error", "req_id": rid, "detail": f"box_local_error: {exc}"})
        )
