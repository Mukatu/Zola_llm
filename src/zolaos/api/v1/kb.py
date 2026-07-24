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

import base64
import binascii
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, current_tenant, optional_principal
from zolaos.db.models import RAG_MODELS
from zolaos.db.session import get_session
from zolaos.rag.ingest import _load_text, ingest_text
from zolaos.rag.retrieval import retrieve
from zolaos.security.pii import PIIRedactionPolicy

router = APIRouter(prefix="/v1/kb", tags=["kb"])

_MIN_TEXTE = 400  # en deçà → PDF probablement scanné → OCR


def _extraire_texte(path: Path) -> str:
    """Extrait le texte (repli OCR fra sur PDF scanné)."""
    texte = _load_text(path)
    if path.suffix.lower() == ".pdf" and len(texte.strip()) < _MIN_TEXTE:
        try:
            import pytesseract
            from pdf2image import convert_from_path

            pages = convert_from_path(str(path), dpi=200)
            texte = "\n\n".join(pytesseract.image_to_string(p, lang="fra") for p in pages)
        except Exception:  # noqa: S110  (OCR indisponible → on garde l'extraction pypdf)
            pass
    return texte


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


def _tenant_filter(schema: str, principal: Principal | None) -> str | None:
    """Corpus privé (rag_tenant) : impose l'isolation par tenant (auth requise).

    Retourne le tag `tenant:<id>` à ajouter au filtre, ou ``None`` pour les corpus
    de référence (consultables sans compte). Lève 401 si rag_tenant sans identité.
    """
    if schema != "rag_tenant":
        return None
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_credentials")
    return principal.tenant_id or "local"


@router.get("/catalog", summary="Facettes de navigation d'un corpus")
async def catalog(
    schema: str = "rag_legal",
    session: AsyncSession = Depends(get_session),
    principal: Principal | None = Depends(optional_principal),
) -> dict[str, Any]:
    model = _model(schema)
    tenant = _tenant_filter(schema, principal)

    tag_q = select(func.unnest(model.tags).label("tag"))
    total_q = select(func.count(func.distinct(model.source_uri)))
    if tenant:
        scope = model.tags.op("@>")([f"tenant:{tenant}"])
        tag_q = tag_q.where(scope)
        total_q = total_q.where(scope)
    sub = tag_q.subquery()
    rows = (
        await session.execute(select(sub.c.tag, func.count().label("n")).group_by(sub.c.tag))
    ).all()

    facettes: dict[str, list[dict[str, Any]]] = {"module": [], "secteur": [], "acte": []}
    for tag, n in rows:
        for prefixe, cle in (("module:", "module"), ("secteur:", "secteur"), ("acte:", "acte")):
            if tag.startswith(prefixe):
                facettes[cle].append({"valeur": tag[len(prefixe) :], "n": int(n)})
    for cle in facettes:
        facettes[cle].sort(key=lambda x: x["valeur"])

    total = (await session.execute(total_q)).scalar_one()
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
    principal: Principal | None = Depends(optional_principal),
) -> dict[str, Any]:
    model = _model(schema)
    req = _required_tags(country, module, secteur, acte)
    tenant = _tenant_filter(schema, principal)
    if tenant:
        req.append(f"tenant:{tenant}")
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
    principal: Principal | None = Depends(optional_principal),
) -> dict[str, Any]:
    model = _model(schema)
    tenant = _tenant_filter(schema, principal)
    stmt = (
        select(model.content, model.extra_metadata, model.source_id)
        .where(model.source_uri == source_uri)
        .order_by(model.chunk_index)
    )
    if tenant:
        stmt = stmt.where(model.tags.op("@>")([f"tenant:{tenant}"]))
    rows = (await session.execute(stmt)).all()
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
async def search(
    body: KbSearchIn,
    principal: Principal | None = Depends(optional_principal),
) -> dict[str, Any]:
    _model(body.schema_rag)
    req = _required_tags(body.country, body.module, body.secteur, body.acte)
    tenant = _tenant_filter(body.schema_rag, principal)
    if tenant:
        req.append(f"tenant:{tenant}")
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


# --------------------------------------------------------------------------
# Documents du CLIENT (rag_tenant) : téléversement + suppression
# --------------------------------------------------------------------------


class KbUploadIn(BaseModel):
    """Téléversement d'un document (contenu encodé base64 — évite le multipart)."""

    filename: str = Field(..., min_length=1)
    content_b64: str = Field(..., min_length=1)
    module: str
    doctype: str
    secteur: str | None = None
    langue: str | None = None
    pii: str = "none"


@router.post("/upload", summary="Téléverser un document contextuel (corpus du client)")
async def upload(
    body: KbUploadIn,
    tenant: str = Depends(current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Ingestion d'un document du client dans le corpus **rag_tenant** (cloisonné
    par ``tenant:<id>``). Décodage base64, extraction texte + repli OCR, chunk,
    embed, insert.
    """
    if body.pii not in {p.value for p in PIIRedactionPolicy}:
        raise HTTPException(status_code=422, detail=f"politique PII invalide: {body.pii!r}")
    try:
        data = base64.b64decode(body.content_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="content_b64 invalide") from exc

    suffixe = Path(body.filename).suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffixe)
    tmp.write(data)
    tmp.close()
    chemin = Path(tmp.name)
    try:
        texte = _extraire_texte(chemin)
        if len(texte.strip()) < 20:
            raise HTTPException(
                status_code=422,
                detail="aucun texte exploitable extrait (document vide ou scan illisible ?)",
            )
        source_uri = f"tenant://{tenant}/{body.module}/{body.doctype}/{body.filename}"
        tags = [
            f"tenant:{tenant}",
            f"module:{body.module}",
            f"doctype:{body.doctype}",
            "country:cg",
        ]
        if body.secteur:
            tags.append(f"secteur:{body.secteur}")
        if body.langue:
            tags.append(f"langue:{body.langue}")
        n = await ingest_text(
            text=texte,
            source_uri=source_uri,
            schema="rag_tenant",
            tags=tags,
            pii_policy=PIIRedactionPolicy(body.pii),
            source_id=body.filename,
            extra_metadata={
                "tenant_id": tenant,
                "module": body.module,
                "doctype": body.doctype,
                "titre": body.filename,
                "secteur": body.secteur,
                "langue": body.langue,
            },
            session=session,
        )
        await session.commit()
    finally:
        os.unlink(chemin)
    return {
        "source_uri": source_uri,
        "titre": body.filename,
        "chunks": n,
        "tenant_id": tenant,
    }


@router.delete("/document", summary="Supprimer un document du client")
async def supprimer(
    source_uri: str = Query(...),
    tenant: str = Depends(current_tenant),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Supprime un document téléversé (rag_tenant uniquement, borné au tenant)."""
    model = RAG_MODELS["rag_tenant"]
    res = await session.execute(
        sa_delete(model)
        .where(model.source_uri == source_uri)
        .where(model.tags.op("@>")([f"tenant:{tenant}"]))
    )
    await session.commit()
    n = res.rowcount or 0
    if n == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document introuvable")
    return {"deleted": source_uri, "chunks": n}
