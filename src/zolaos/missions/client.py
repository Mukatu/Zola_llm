"""Client `MissionClient` — utilisé par Zolacortex pour interroger une Zolabox distante.

Profil **cortex obligatoire**. Wrap httpx async + JWT mission + retries simples.

## Architecture Zero Trust Client (acté 2026-05-18)

Ce client est **strictement read-only sur le RAG** (`rag_search()`). Il ne fait :
- ❌ JAMAIS d'inférence LLM proxy via la Box (les prompts cabinet ne doivent
  jamais quitter le Cortex Polaris)
- ❌ JAMAIS d'écriture sur la Box (la Box est strictement local au client)
- ✅ Uniquement la récupération de chunks RAG anonymisés (PII redaction
  pré-ingestion garantit qu'aucune identité ne fuit)

Tout ajout futur de méthode à ce client doit respecter cette règle : pas de
proxy d'inférence LLM, pas d'écriture distante. Si un overlay Polaris a besoin
d'inférence, elle se fait CHEZ POLARIS (LLM_HOST_ROUTER côté Cortex), jamais
en transitant via la Box client.

Voir `project_zero_trust_client_architecture.md` pour le rationale complet.

## Usage type

    async with MissionClient(
        box_url="https://box-clientx.local",
        mission_token="eyJ...",
    ) as client:
        matches = await client.rag_search(
            schema="rag_legal",
            query="Comment renouveler une période d'essai cadre ?",
            required_tags=["country:cg", "module:travail_cg"],
            k=5,
        )
        # Les `matches` (chunks anonymisés) sont ensuite passés à l'overlay
        # Polaris pour inférence locale Cortex avec son prompt secret cabinet.
"""

from __future__ import annotations

from typing import Any

import httpx

from zolaos.core.logging import get_logger
from zolaos.core.profiles import Profile, require_profile

_log = get_logger("zolaos.missions.client")


class MissionClientError(RuntimeError):
    """Erreur d'appel à une Zolabox distante (réseau, 4xx, 5xx)."""


class MissionClient:
    """Client HTTP async vers une Zolabox cliente. Authentifié par JWT mission."""

    def __init__(
        self,
        *,
        box_url: str,
        mission_token: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        # Vérification de profil à l'instanciation : impossible d'utiliser un
        # MissionClient depuis un Zolabox.
        require_profile(Profile.CORTEX)
        self._box_url = box_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._box_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            headers={"Authorization": f"Bearer {mission_token}"},
        )

    async def __aenter__(self) -> MissionClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rag_search(
        self,
        *,
        schema: str,
        query: str,
        required_tags: list[str] | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Délègue la recherche RAG à la Zolabox du client. Retourne `matches`."""
        body: dict[str, Any] = {
            "schema": schema,
            "query": query,
            "required_tags": required_tags or [],
            "k": k,
        }
        try:
            r = await self._client.post("/v1/box/rag/search", json=body)
        except httpx.HTTPError as exc:
            raise MissionClientError(f"Box injoignable : {exc}") from exc

        if r.status_code == 401:
            raise MissionClientError("Mission token rejetée (401)")
        if r.status_code == 403:
            raise MissionClientError(f"Hors scope mission (403): {r.text}")
        if r.status_code >= 400:
            raise MissionClientError(f"Erreur Box ({r.status_code}): {r.text}")

        data = r.json()
        _log.info(
            "mission_client.rag_search",
            mission_id=data.get("mission_id"),
            request_id=data.get("request_id"),
            schema=schema,
            hits=len(data.get("matches", [])),
        )
        return data.get("matches", [])
