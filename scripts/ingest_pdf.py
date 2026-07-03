#!/usr/bin/env python
"""Ingestion d'un document (PDF ou autre format supporté) dans un schéma RAG.

Télécharge une **URL** (ou lit un **fichier local**), extrait le texte (PDF via
pypdf ; .docx/.html/.csv/.xlsx/.txt/.md aussi, via le loader RAG), découpe et
ingère dans le schéma cible. Pensé pour les **sources officielles** (CGI, Code du
travail, SYCEBNL, LNME…) qui ne sont pas des datasets HuggingFace.

- Idempotent : clé `(source_uri, chunk_index)` + `ON CONFLICT DO NOTHING`.
- Rôle d'ingestion = **migrator** (propriétaire des schémas `rag_*` ; l'app n'a
  que le SELECT — zero-trust).
- `--dry-run` : télécharge + extrait + découpe et affiche un aperçu **sans base
  ni embeddings** (testable même sans le modèle bge-m3).
- L'ingestion réelle nécessite bge-m3 (cf. `docs/RAG_INGESTION.md`).

Exemples :
    python scripts/ingest_pdf.py --url https://www.sgg.cg/.../sycebnl.pdf \
        --schema rag_erp --source-id sycebnl \
        --tags country:cg,module:projets_ong,type:texte_legal --dry-run

    python scripts/ingest_pdf.py --file /tmp/cgi_cg.pdf --schema rag_legal \
        --source-id cgi_cg --tags country:cg,module:fiscal_cg,type:texte_legal
"""

from __future__ import annotations

import os

# Offline-first : on utilise le modèle/tokenizer bge-m3 baké dans l'image
# (cf. Dockerfile) sans recheck réseau du Hub (qui stalle sur le throttle
# anonyme). Le PDF, lui, est récupéré en HTTP direct. Surchargeable via l'env.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse
import asyncio
import tempfile
import time
import urllib.request
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.settings import Settings, get_settings
from zolaos.rag.chunking import get_chunker
from zolaos.rag.ingest import _load_text, ingest_text
from zolaos.security.pii import PIIRedactionPolicy

_UA = "Mozilla/5.0 (ZolaOS ingestion bot)"
_MIN_TEXTE = 400  # en deçà → PDF probablement scanné (image) → OCR


def _ocr_pdf(path: Path, lang: str = "fra") -> str:
    """OCR d'un PDF scanné (image) via pdf2image (poppler) + tesseract.

    Beaucoup de textes officiels congolais (conventions collectives, décrets
    anciens) sont diffusés en scans image sans couche texte : pypdf n'en extrait
    rien, il faut les reconnaître optiquement.
    """
    import pytesseract
    from pdf2image import convert_from_path

    pages = convert_from_path(str(path), dpi=200)
    return "\n\n".join(pytesseract.image_to_string(img, lang=lang) for img in pages)


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire des schémas rag_*)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


def _telecharger(url: str, tentatives: int = 5) -> Path:
    """Télécharge l'URL vers un fichier temporaire (suffixe déduit de l'URL).

    Réessaie sur erreur réseau/DNS transitoire (backoff croissant, ~45 s au total)
    pour survivre aux coupures DNS intermittentes observées dans certains bacs à sable.
    """
    suffixe = Path(url.split("?", 1)[0]).suffix or ".pdf"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})  # noqa: S310
    dernier: OSError | None = None
    for essai in range(tentatives):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffixe)
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (URL admin)
                tmp.write(r.read())
            tmp.close()
            return Path(tmp.name)
        except OSError as e:  # URLError et socket.gaierror héritent d'OSError
            dernier = e
            time.sleep(3 * (essai + 1))
    raise RuntimeError(f"Téléchargement échoué après {tentatives} tentatives : {url}") from dernier


def _resoudre_source(url: str | None, fichier: str | None) -> tuple[Path, str]:
    """Retourne (chemin local, source_uri). Télécharge si URL."""
    if url:
        return _telecharger(url), url
    assert fichier is not None
    p = Path(fichier)
    if not p.exists():
        raise FileNotFoundError(p)
    return p, p.resolve().as_uri()


async def ingerer(
    *,
    url: str | None,
    fichier: str | None,
    schema: str,
    tags: list[str],
    source_id: str,
    pii: PIIRedactionPolicy,
    dry_run: bool,
    ocr: bool = True,
    ocr_lang: str = "fra",
) -> None:
    chemin, source_uri = _resoudre_source(url, fichier)
    texte = _load_text(chemin)
    print(f"Document : {source_uri}\n  {len(texte)} caractères extraits.")

    # Repli OCR : PDF scanné (image) sans couche texte exploitable.
    if ocr and chemin.suffix.lower() == ".pdf" and len(texte.strip()) < _MIN_TEXTE:
        print(f"  extraction insuffisante (<{_MIN_TEXTE}) → OCR ({ocr_lang})…")
        texte = _ocr_pdf(chemin, lang=ocr_lang)
        print(f"  OCR : {len(texte)} caractères reconnus.")

    chunks = get_chunker().chunk(texte)
    print(f"  {len(chunks)} chunks (schéma={schema}, tags={tags}, pii={pii.value}).")

    if dry_run:
        if chunks:
            apercu = chunks[0].text.strip().replace("\n", " ")
            print(f"  aperçu chunk[0] : {apercu[:200]}…")
        print("  (dry-run : aucune écriture, aucun embedding)")
        return

    settings = get_settings()
    engine = create_async_engine(_dsn_async_migrator(settings), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            n = await ingest_text(
                text=texte,
                source_uri=source_uri,
                schema=schema,
                tags=tags,
                pii_policy=pii,
                source_id=source_id,
                extra_metadata={"source_uri": source_uri, "source_id": source_id},
                session=session,
            )
            await session.commit()
    finally:
        await engine.dispose()
    print(f"Terminé : {n} chunks insérés dans {schema}.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Ingestion d'un document (URL/fichier) → schéma RAG")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="URL du document (PDF, etc.)")
    src.add_argument("--file", help="chemin d'un fichier local")
    p.add_argument(
        "--schema", required=True, help="schéma RAG cible (rag_legal, rag_erp, rag_health…)"
    )
    p.add_argument(
        "--tags",
        required=True,
        help="tags séparés par des virgules (inclure country:cg + module:<m>)",
    )
    p.add_argument("--source-id", required=True, help="identifiant stable de la source")
    p.add_argument(
        "--pii",
        default="none",
        choices=[pol.value for pol in PIIRedactionPolicy],
        help="politique PII (none pour texte public)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="extraire + découper sans écrire ni embed"
    )
    p.add_argument("--no-ocr", action="store_true", help="désactiver le repli OCR sur PDF scanné")
    p.add_argument("--ocr-lang", default="fra", help="langue tesseract pour l'OCR (défaut : fra)")
    args = p.parse_args()

    asyncio.run(
        ingerer(
            url=args.url,
            fichier=args.file,
            schema=args.schema,
            tags=[t.strip() for t in args.tags.split(",") if t.strip()],
            source_id=args.source_id,
            pii=PIIRedactionPolicy(args.pii),
            dry_run=args.dry_run,
            ocr=not args.no_ocr,
            ocr_lang=args.ocr_lang,
        )
    )
