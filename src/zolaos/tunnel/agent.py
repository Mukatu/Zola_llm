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
from typing import Any

import httpx
import websockets

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings

_log = get_logger("zolaos.tunnel.agent")


async def run_box_tunnel_agent(settings: Settings) -> None:
    """Boucle de vie de l'agent : connexion, service, reconnexion sur coupure."""
    url = settings.TUNNEL_CORTEX_URL
    tenant_id = settings.ZOLAOS_BOX_TENANT_ID
    credential = settings.ZOLAOS_BOX_CREDENTIAL.get_secret_value()
    if not url or not tenant_id or not credential:
        _log.warning("tunnel.agent.disabled", reason="config_incomplete")
        return

    local_base = f"http://localhost:{settings.APP_PORT}"
    backoff = settings.TUNNEL_RECONNECT_SECONDS

    while True:
        try:
            async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
                await ws.send(
                    json.dumps({"type": "hello", "tenant_id": tenant_id, "credential": credential})
                )
                _log.info("tunnel.agent.connected", cortex=url, tenant_id=tenant_id)
                async with httpx.AsyncClient(base_url=local_base, timeout=httpx.Timeout(30.0)) as http:
                    async for raw in ws:
                        await _handle_frame(ws, http, raw)
        except asyncio.CancelledError:
            _log.info("tunnel.agent.stopped")
            raise
        except Exception as exc:  # coupure réseau, cortex indispo, etc.
            _log.warning("tunnel.agent.disconnected", error=str(exc))
            await asyncio.sleep(backoff)


async def _handle_frame(ws: Any, http: httpx.AsyncClient, raw: str | bytes) -> None:
    """Relaie une requête du Cortex vers l'API box locale, renvoie la réponse."""
    try:
        msg = json.loads(raw)
    except Exception:
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
            await ws.send(json.dumps({"type": "error", "req_id": rid, "detail": f"box_{r.status_code}: {r.text[:200]}"}))
            return
        data = r.json()
        await ws.send(json.dumps({"type": "rag_result", "req_id": rid, "matches": data.get("matches", [])}))
    except Exception as exc:
        await ws.send(json.dumps({"type": "error", "req_id": rid, "detail": f"box_local_error: {exc}"}))
