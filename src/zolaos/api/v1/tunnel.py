"""Point d'entrée WebSocket du tunnel inverse — côté CORTEX.

La Zolabox appelle ``/v1/tunnel/connect`` (connexion sortante), s'authentifie par
secret partagé + identité de tenant, et le canal est enregistré dans ``REGISTRY``.
Le Cortex y poussera ensuite les requêtes RAG de mission (cf. run_audit).

Monté uniquement en profil ``cortex`` (c'est le seul port entrant, côté Polaris ;
côté client, aucun port n'est ouvert).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from zolaos.core.logging import get_logger
from zolaos.core.settings import get_settings
from zolaos.tunnel.channel import REGISTRY, TunnelChannel

_log = get_logger("zolaos.api.v1.tunnel")

router = APIRouter(tags=["tunnel"])


@router.websocket("/v1/tunnel/connect")
async def tunnel_connect(ws: WebSocket) -> None:
    await ws.accept()
    secret = get_settings().TUNNEL_SHARED_SECRET.get_secret_value()

    try:
        hello = await ws.receive_json()
    except Exception:
        await ws.close(code=4400)
        return

    if not secret or hello.get("secret") != secret or not hello.get("tenant_id"):
        _log.warning("tunnel.reject", reason="bad_hello")
        await ws.close(code=4401)
        return

    tenant_id = str(hello["tenant_id"])
    channel = TunnelChannel(tenant_id, ws)
    REGISTRY[tenant_id] = channel  # une box par tenant : la nouvelle remplace l'ancienne
    _log.info("tunnel.box_connected", tenant_id=tenant_id)

    try:
        await channel.serve()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        _log.warning("tunnel.channel_error", tenant_id=tenant_id, error=str(exc))
    finally:
        channel.cancel_pending()
        if REGISTRY.get(tenant_id) is channel:
            REGISTRY.pop(tenant_id, None)
        _log.info("tunnel.box_disconnected", tenant_id=tenant_id)
