"""Tunnel inverse Zolabox → Zolacortex — côté CORTEX (déploiement hybride).

La Zolabox est derrière le pare-feu du client : elle ouvre une connexion WebSocket
**sortante** vers le Cortex et la maintient. Le Cortex ne se connecte JAMAIS à la
box ; il pousse les requêtes RAG de mission DANS ce canal, la box les sert
localement et répond. Le jeton de mission gouverne toujours l'accès réel aux
données — le tunnel n'est que le transport.

Ce module tient, côté Cortex :
- un ``TunnelChannel`` par box connectée (multiplexage requête/réponse par ``req_id``) ;
- un ``REGISTRY`` ``tenant_id → channel`` (runtime, en mémoire) ;
- ``TunnelRagClient``, compatible avec l'interface de ``MissionClient`` (``rag_search``),
  pour que l'audit route ses recherches par le tunnel sans code spécifique.

Limite (durcissement prod) : registre en mémoire, mono-process ; une box par tenant.
Un cluster Cortex multi-worker nécessiterait un routage partagé (Redis/pub-sub).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.tunnel.channel")

# tenant_id (str) → canal vivant. Rempli à la connexion d'une box, vidé à sa coupure.
REGISTRY: dict[str, "TunnelChannel"] = {}


class TunnelError(RuntimeError):
    """Échec d'une requête servie via le tunnel (timeout, box en erreur, coupure)."""


class TunnelChannel:
    """Un canal WebSocket vers une box. Corrèle réponses ↔ requêtes par ``req_id``."""

    def __init__(self, tenant_id: str, ws: Any) -> None:
        self._tenant_id = tenant_id
        self._ws = ws  # starlette.websockets.WebSocket
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._send_lock = asyncio.Lock()

    async def serve(self) -> None:
        """Boucle de réception : résout les futures des réponses par ``req_id``.

        Tourne tant que la box reste connectée. Lève à la déconnexion (géré par
        l'appelant, qui retire le canal du registre).
        """
        while True:
            raw = await self._ws.receive_text()
            try:
                msg = _loads(raw)
            except Exception:  # trame illisible : on ignore, sans casser le canal
                continue
            rid = msg.get("req_id")
            fut = self._pending.pop(rid, None) if rid else None
            if fut is not None and not fut.done():
                fut.set_result(msg)

    async def rag_search(
        self,
        *,
        mission_token: str,
        schema: str,
        query: str,
        required_tags: list[str] | None,
        k: int,
        timeout: float,
    ) -> list[dict[str, Any]]:
        """Envoie une requête RAG dans le tunnel et attend la réponse de la box."""
        rid = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[rid] = fut
        frame = _dumps(
            {
                "type": "rag_search",
                "req_id": rid,
                "mission_token": mission_token,
                "schema": schema,
                "query": query,
                "required_tags": required_tags or [],
                "k": k,
            }
        )
        try:
            async with self._send_lock:
                await self._ws.send_text(frame)
            resp = await asyncio.wait_for(fut, timeout)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise TunnelError("box_timeout") from exc
        except Exception as exc:  # canal coupé pendant l'échange
            raise TunnelError(f"tunnel_broken: {exc}") from exc
        finally:
            self._pending.pop(rid, None)

        if resp.get("type") == "error":
            raise TunnelError(str(resp.get("detail", "box_error")))
        return list(resp.get("matches", []))

    def cancel_pending(self) -> None:
        """À la coupure : réveille toutes les requêtes en attente en erreur."""
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(TunnelError("tunnel_closed"))
        self._pending.clear()

    async def close(self) -> None:
        """Ferme le canal (utilisé lors d'une révocation : coupe la box immédiatement)."""
        try:
            await self._ws.close(code=4403)
        except Exception:  # déjà fermé / en cours de fermeture
            pass


async def disconnect_tenant(tenant_id: str) -> bool:
    """Coupe la connexion vivante d'un tenant (révocation immédiate). True si coupée."""
    channel = REGISTRY.get(tenant_id)
    if channel is None:
        return False
    await channel.close()
    return True


class TunnelRagClient:
    """Adaptateur compatible ``MissionClient`` : ``rag_search`` route par le tunnel.

    Permet de réutiliser tel quel le pipeline de l'overlay (qui appelle
    ``mission_client.rag_search``) sans le savoir branché sur un tunnel.
    """

    def __init__(self, channel: TunnelChannel, mission_token: str, timeout: float) -> None:
        self._channel = channel
        self._token = mission_token
        self._timeout = timeout

    async def __aenter__(self) -> "TunnelRagClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def rag_search(
        self,
        *,
        schema: str,
        query: str,
        required_tags: list[str] | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        return await self._channel.rag_search(
            mission_token=self._token,
            schema=schema,
            query=query,
            required_tags=required_tags,
            k=k,
            timeout=self._timeout,
        )


# JSON local (évite d'imposer orjson ici ; les trames sont petites).
import json  # noqa: E402


def _dumps(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(raw: str) -> dict[str, Any]:
    return json.loads(raw)
