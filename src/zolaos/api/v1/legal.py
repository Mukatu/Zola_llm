"""Pôle juridique — outils (traduction de contrats étrangers).

La traduction est une **capacité à part entière** : un contrat en langue
étrangère (paste ou fichier téléversé) est traduit fidèlement en français, puis
peut être **assimilé** dans le corpus du client (rag_tenant) pour que l'assistant
réponde dessus. Nécessite le LLM (8B) au runtime.
"""

from __future__ import annotations

import base64
import binascii
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.agents.legal.translation import TranslationService
from zolaos.api.dependencies import get_router_client
from zolaos.api.v1.kb import _extraire_texte
from zolaos.core.settings import Settings, get_settings
from zolaos.db.session import get_session
from zolaos.llm.base import LLMClient
from zolaos.rag.ingest import ingest_text
from zolaos.security.pii import PIIRedactionPolicy

router = APIRouter(prefix="/v1/legal", tags=["legal"])


class TranslateIn(BaseModel):
    """Texte OU fichier (base64) à traduire. Assimilation optionnelle."""

    text: str | None = None
    filename: str | None = None
    content_b64: str | None = None
    target_lang: str = "français"
    source_lang: str | None = None
    assimilate: bool = False
    tenant_id: str = "local"
    module: str = "ohada"


def _texte_depuis(body: TranslateIn) -> tuple[str, str | None]:
    """Retourne (texte, titre) depuis le champ text ou le fichier base64."""
    if body.text and body.text.strip():
        return body.text, None
    if body.content_b64 and body.filename:
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
            return _extraire_texte(chemin), body.filename
        finally:
            os.unlink(chemin)
    raise HTTPException(status_code=422, detail="fournir 'text' ou ('filename' + 'content_b64')")


@router.post("/translate", summary="Traduire un contrat étranger (texte ou fichier)")
async def translate(
    body: TranslateIn,
    client: LLMClient = Depends(get_router_client),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    texte, titre = _texte_depuis(body)
    if len(texte.strip()) < 5:
        raise HTTPException(status_code=422, detail="texte à traduire trop court / vide")

    svc = TranslationService(client, settings)
    res = await svc.translate(texte, target_lang=body.target_lang, source_lang=body.source_lang)

    out: dict[str, Any] = {
        "source_lang": res.source_lang,
        "target_lang": res.target_lang,
        "translation": res.text,
        "caracteres": len(res.text),
        "assimilated": False,
    }

    if body.assimilate:
        source_uri = f"tenant://{body.tenant_id}/{body.module}/traduction/{titre or 'texte'}"
        n = await ingest_text(
            text=res.text,
            source_uri=source_uri,
            schema="rag_tenant",
            tags=[
                f"tenant:{body.tenant_id}",
                f"module:{body.module}",
                "doctype:traduction",
                f"langue:{body.target_lang}",
                f"source_langue:{res.source_lang}",
                "country:cg",
            ],
            pii_policy=PIIRedactionPolicy.NONE,
            source_id=titre or "traduction",
            extra_metadata={
                "tenant_id": body.tenant_id,
                "doctype": "traduction",
                "titre": f"Traduction — {titre or 'texte'}",
                "langue": body.target_lang,
                "source_langue": res.source_lang,
            },
            session=session,
        )
        await session.commit()
        out.update({"assimilated": True, "source_uri": source_uri, "chunks": n})

    return out
