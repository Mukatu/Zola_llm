"""Point d'entrée WebSocket du tunnel inverse — côté CORTEX.

La Zolabox appelle ``/v1/tunnel/connect`` (connexion sortante) et s'authentifie avec
son **credential par box** (unique, révocable) : le handshake le vérifie contre le
hash stocké sur le tenant (``box_credential_hash``). Le canal est ensuite enregistré
dans ``REGISTRY`` ; le Cortex y poussera les requêtes RAG de mission (cf. run_audit).

Monté uniquement en profil ``cortex`` (seul port entrant, côté Polaris ; côté client,
aucun port n'est ouvert). En production, le WebSocket passe en ``wss://`` avec
terminaison mTLS au reverse-proxy (cf. docs/PRODUCTION_HYBRID.md) — cette
vérification applicative par credential vient EN PLUS de la couche transport.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from zolaos.core.logging import get_logger
from zolaos.core.security import verify_box_credential
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import Tenant
from zolaos.db.session import get_session_factory
from zolaos.tunnel.channel import REGISTRY, TunnelChannel

_log = get_logger("zolaos.api.v1.tunnel")

router = APIRouter(tags=["tunnel"])


async def _verify_box(tenant_id: str, credential: str, settings: Settings) -> bool:
    """Vrai si le credential correspond au hash actif du tenant (constant-time)."""
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        return False
    pepper = settings.API_KEY_PEPPER.get_secret_value()
    if not pepper or not credential:
        return False
    async with get_session_factory()() as session:
        tenant = await session.get(Tenant, tenant_uuid)
    if tenant is None or not tenant.is_active or not tenant.box_credential_hash:
        return False
    return verify_box_credential(credential, tenant.box_credential_hash, pepper=pepper)


@router.websocket("/v1/tunnel/connect")
async def tunnel_connect(ws: WebSocket) -> None:
    await ws.accept()
    settings = get_settings()

    try:
        hello = await ws.receive_json()
    except Exception:
        await ws.close(code=4400)
        return

    tenant_id = str(hello.get("tenant_id") or "")
    credential = str(hello.get("credential") or "")
    if not tenant_id or not await _verify_box(tenant_id, credential, settings):
        _log.warning("tunnel.reject", tenant_id=tenant_id or "?", reason="bad_credential")
        await ws.close(code=4401)
        return

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
