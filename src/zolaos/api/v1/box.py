"""Endpoints Zolabox exposés au Cortex Polaris (Polaris-8).

Routes :
  - `POST /v1/box/rag/search` : recherche RAG top-k, lecture seule, scopée par
    les tags de la mission. Audit hash systématique.

Sécurité :
  - Profil `box` exclusivement (les routes ne sont pas montées en profil cortex).
  - Authorization: `Bearer <mission JWT>` — vérifié + croisé avec `core.missions`.
  - Toute requête est journalisée dans `audit.log` (chaîne hash chez le client).
  - **Lecture seule** — aucune écriture distante autorisée.
  - Le `scope_tags` du JWT INTERSECTE les `required_tags` pour empêcher un
    consultant d'élargir son périmètre au-delà de ce qui a été validé en mission.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_box
from zolaos.core.settings import Settings, get_settings
from zolaos.db.session import get_session
from zolaos.missions.audit import audit_box_access
from zolaos.missions.tokens import MissionClaims, MissionTokenError, verify_mission_token
from zolaos.rag.retrieval import Match, retrieve

_log = get_logger("zolaos.api.v1.box")

router = APIRouter(prefix="/v1/box", tags=["box"], dependencies=[Depends(require_box)])


# ---------------------------------------------------------------------------
# Dépendance : extraction + vérification du JWT mission
# ---------------------------------------------------------------------------


async def _mission_claims(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MissionClaims:
    """Vérifie le header Authorization Bearer et retourne les claims mission validés."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
            headers={"WWW-Authenticate": 'Bearer realm="mission"'},
        )
    token = authorization[7:].strip()
    try:
        return await verify_mission_token(token, session=session, settings=settings)
    except MissionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid_mission_token: {exc}",
            headers={"WWW-Authenticate": 'Bearer realm="mission"'},
        ) from exc


# ---------------------------------------------------------------------------
# Schémas I/O
# ---------------------------------------------------------------------------


class RagSearchRequest(BaseModel):
    schema_name: str = Field(..., alias="schema", description="rag_health | rag_legal")
    query: str = Field(..., min_length=1, max_length=2000)
    required_tags: list[str] = Field(
        default_factory=list,
        description="Tags demandés pour la recherche. Seront intersectés avec scope_tags du JWT.",
    )
    k: int = Field(default=5, ge=1, le=20)

    model_config = {"populate_by_name": True}


class RagMatchOut(BaseModel):
    content: str
    score: float
    similarity: float
    source_uri: str
    source_id: str | None
    chunk_index: int
    tags: list[str]


class RagSearchResponse(BaseModel):
    request_id: str
    mission_id: str
    schema_name: str = Field(..., alias="schema")
    effective_tags: list[str]
    matches: list[RagMatchOut]

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/rag/search",
    response_model=RagSearchResponse,
    summary="Recherche RAG depuis Zolacortex via JWT mission",
    description=(
        "Profil `box` uniquement. Authorization: Bearer <mission JWT>.\n\n"
        "Les `required_tags` sont **intersectés avec `scope_tags` du JWT** : un consultant "
        "ne peut pas requêter au-delà du périmètre validé en mission. Toute requête est "
        "tracée dans audit.log (chaîne hash inviolable côté DB)."
    ),
)
async def rag_search(
    body: RagSearchRequest,
    claims: Annotated[MissionClaims, Depends(_mission_claims)],
    session: AsyncSession = Depends(get_session),
) -> RagSearchResponse:
    # Intersection scope mission ∩ tags demandés → tags effectifs.
    # On exige au minimum un tag (anti-leak comme `retrieve`), en plus du scope mission.
    scope = set(claims.scope_tags)
    requested = set(body.required_tags)

    if not scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="mission_scope_empty",
        )

    # Si l'appelant ne demande pas de tags spécifiques, on applique le scope mission tel quel.
    if not requested:
        effective = sorted(scope)
    else:
        # Sinon, on EXIGE que les tags demandés soient TOUS inclus dans le scope mission.
        # Sinon → 403 (le consultant tente de sortir du périmètre).
        if not requested.issubset(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"tags_outside_mission_scope: {sorted(requested - scope)}",
            )
        effective = sorted(requested)

    request_id = uuid.uuid4()

    try:
        matches: list[Match] = await retrieve(
            query=body.query,
            schema=body.schema_name,
            required_tags=effective,
            k=body.k,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Audit hash : journalisation immuable côté client.
    await audit_box_access(
        session=session,
        claims=claims,
        event="box_rag_search",
        request_id=request_id,
        payload_extra={
            "schema": body.schema_name,
            "query_preview": body.query[:200],
            "effective_tags": effective,
            "k": body.k,
            "matches_count": len(matches),
            "top_similarity": matches[0].similarity if matches else None,
        },
    )
    await session.commit()

    return RagSearchResponse(
        request_id=str(request_id),
        mission_id=str(claims.mission_id),
        schema=body.schema_name,
        effective_tags=effective,
        matches=[
            RagMatchOut(
                content=m.content,
                score=m.score,
                similarity=m.similarity,
                source_uri=m.source_uri,
                source_id=m.source_id,
                chunk_index=m.chunk_index,
                tags=m.tags,
            )
            for m in matches
        ],
    )
