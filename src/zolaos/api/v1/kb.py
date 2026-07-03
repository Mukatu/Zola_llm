"""Bibliothèque documentaire — consultation directe des corpus RAG (lecture seule).

Permet à l'utilisateur de **naviguer et lire** les textes sources ingérés
(Actes uniformes, conventions collectives, CGI, LNME…), pas seulement de recevoir
des réponses d'agents. Réutilise le même corpus RAG (un corpus, deux usages :
ancrage des agents + consultation humaine).

Endpoints (transverse box + cortex, lecture seule via le rôle app — SELECT sur rag_*) :
- GET  /v1/kb/catalog?schema=            → facettes (module / secteur / acte) + nb documents
- GET  /v1/kb/documents?schema=&module=… → liste des documents (filtrable)
- GET  /v1/kb/document?schema=&source_uri= → texte reconstitué d'un document
- POST /v1/kb/search                      → recherche sémantique (embeddings) filtrée

RBAC : `country:cg` toujours imposé. La recherche sémantique nécessite le modèle
d'embeddings (bge-m3) ; la navigation et la lecture fonctionnent sans.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.db.models import RAG_MODELS
from zolaos.db.session import get_session
from zolaos.rag.retrieval import retrieve

router = APIRouter(prefix="/v1/kb", tags=["kb"])


def _model(schema: str) -> Any:
    if schema not in RAG_MODELS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"schéma RAG inconnu: {schema!r}. Connus: {list(RAG_MODELS)}",
        )
    return RAG_MODELS[schema]


def _required_tags(
    country: str, module: str | None, secteur: str | None, acte: str | None
) -> list[str]:
    tags = [f"country:{country}"]
    if module:
        tags.append(f"module:{module}")
    if secteur:
        tags.append(f"secteur:{secteur}")
    if acte:
        tags.append(f"acte:{acte}")
    return tags


def _titre(meta: dict[str, Any] | None, source_id: str | None) -> str | None:
    m = meta or {}
    return m.get("titre") or m.get("acte_nom") or source_id


@router.get("/catalog", summary="Facettes de navigation d'un corpus")
async def catalog(
    schema: str = "rag_legal",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    model = _model(schema)
    sub = select(func.unnest(model.tags).label("tag")).subquery()
    rows = (await session.execute(select(sub.c.tag, func.count().label("n")).group_by(sub.c.tag))).all()

    facettes: dict[str, list[dict[str, Any]]] = {"module": [], "secteur": [], "acte": []}
    for tag, n in rows:
        for prefixe, cle in (("module:", "module"), ("secteur:", "secteur"), ("acte:", "acte")):
            if tag.startswith(prefixe):
                facettes[cle].append({"valeur": tag[len(prefixe) :], "n": int(n)})
    for cle in facettes:
        facettes[cle].sort(key=lambda x: x["valeur"])

    total = (
        await session.execute(select(func.count(func.distinct(model.source_uri))))
    ).scalar_one()
    return {"schema": schema, "documents": int(total), "facettes": facettes}


@router.get("/documents", summary="Liste des documents d'un corpus (filtrable)")
async def documents(
    schema: str = "rag_legal",
    module: str | None = None,
    secteur: str | None = None,
    acte: str | None = None,
    country: str = "cg",
    limit: int = Query(default=300, le=1000),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    model = _model(schema)
    req = _required_tags(country, module, secteur, acte)
    stmt = (
        select(
            model.source_uri,
            model.source_id,
            model.extra_metadata,
            func.count().over(partition_by=model.source_uri).label("nb"),
        )
        .where(model.tags.op("@>")(req))
        .order_by(model.source_uri, model.chunk_index)
        .distinct(model.source_uri)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    docs = [
        {
            "source_uri": r.source_uri,
            "source_id": r.source_id,
            "titre": _titre(r.extra_metadata, r.source_id),
            "acte": (r.extra_metadata or {}).get("acte"),
            "nb_chunks": int(r.nb),
        }
        for r in rows
    ]
    return {"schema": schema, "total": len(docs), "documents": docs}


@router.get("/document", summary="Texte reconstitué d'un document")
async def document(
    schema: str = "rag_legal",
    source_uri: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    model = _model(schema)
    rows = (
        await session.execute(
            select(model.content, model.extra_metadata, model.source_id)
            .where(model.source_uri == source_uri)
            .order_by(model.chunk_index)
        )
    ).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document introuvable")
    meta = rows[0].extra_metadata or {}
    return {
        "source_uri": source_uri,
        "source_id": rows[0].source_id,
        "titre": _titre(meta, rows[0].source_id),
        "nb_chunks": len(rows),
        "extra_metadata": meta,
        "texte": "\n\n".join(r.content for r in rows),
    }


class KbSearchIn(BaseModel):
    q: str = Field(..., min_length=2)
    schema_rag: str = Field(default="rag_legal", alias="schema")
    module: str | None = None
    secteur: str | None = None
    acte: str | None = None
    country: str = "cg"
    k: int = Field(default=8, ge=1, le=30)

    model_config = {"populate_by_name": True}


@router.post("/search", summary="Recherche sémantique dans un corpus (embeddings)")
async def search(body: KbSearchIn) -> dict[str, Any]:
    _model(body.schema_rag)
    req = _required_tags(body.country, body.module, body.secteur, body.acte)
    matches = await retrieve(query=body.q, schema=body.schema_rag, required_tags=req, k=body.k)
    return {
        "resultats": [
            {
                "source_uri": m.source_uri,
                "source_id": m.source_id,
                "chunk_index": m.chunk_index,
                "similarity": round(m.similarity, 4),
                "extrait": m.content[:400],
            }
            for m in matches
        ]
    }
