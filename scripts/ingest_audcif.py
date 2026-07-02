#!/usr/bin/env python
"""Ingestion du corpus AUDCIF (droit comptable OHADA) dans le schéma RAG `rag_erp`.

Source : dataset HuggingFace ``Maathis-com/ohada-actes-uniformes`` (licence
**CC-BY-4.0**), fichier ``nodes/articles.csv`` filtré sur ``acte_code == 'AUDCIF'``
(Acte uniforme relatif au droit comptable et à l'information financière).
Chaque article devient un document RAG ; l'ingestion est **idempotente** (clé
``source_uri`` unique + ``ON CONFLICT DO NOTHING``), donc ré-exécutable sans
doublon.

Rôle d'ingestion = ``migrator`` (propriétaire du schéma ``rag_erp``). L'app
applicative n'a que le SELECT sur ``rag_*`` (zero-trust), elle ne peut donc pas
ingérer : c'est une opération d'administration, hors chemin applicatif.

Exécution (dans le conteneur applicatif : HF + sentence-transformers + accès DB) :
    python scripts/ingest_audcif.py [--limit N] [--dry-run]

Le premier appel télécharge le modèle d'embeddings ``BAAI/bge-m3`` (~2,3 Go)
puis encode les articles sur CPU.
"""

from __future__ import annotations

import argparse
import asyncio
import csv

from huggingface_hub import hf_hub_download
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from zolaos.core.settings import Settings, get_settings
from zolaos.rag.ingest import ingest_text
from zolaos.security.pii import PIIRedactionPolicy

REPO = "Maathis-com/ohada-actes-uniformes"
ACTE = "AUDCIF"
TAGS = ["country:cg", "module:audcif", "type:texte_legal", "source:ohada"]


def charger_articles_audcif() -> list[dict[str, str]]:
    """Télécharge nodes/articles.csv et retourne les lignes de l'AUDCIF."""
    path = hf_hub_download(REPO, "nodes/articles.csv", repo_type="dataset")
    with open(path, encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if (row.get("acte_code") or "").strip() == ACTE]


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire de rag_erp)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


def _corps_article(a: dict[str, str]) -> tuple[str, str, str]:
    """Retourne (numero, entête lisible, texte complet à ingérer)."""
    num = (a.get("article_number") or "").strip()
    titre = (a.get("titre") or "").strip()
    text = (a.get("text") or "").strip()
    entete = f"AUDCIF — Article {num}" + (f" — {titre}" if titre else "")
    return num, entete, f"{entete}\n\n{text}" if text else ""


async def ingerer(limit: int | None, dry_run: bool) -> None:
    settings = get_settings()
    articles = charger_articles_audcif()
    if limit:
        articles = articles[:limit]
    print(f"AUDCIF : {len(articles)} articles à ingérer (dry_run={dry_run}).")

    if dry_run:
        for a in articles[:3]:
            _, entete, corps = _corps_article(a)
            print(f"  · {entete}\n    {corps[:120]}…")
        return

    engine = create_async_engine(_dsn_async_migrator(settings), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    total_chunks = 0
    ingeres = 0
    try:
        async with sessionmaker() as session:
            for a in articles:
                num, _, corps = _corps_article(a)
                if not corps:
                    continue
                n = await ingest_text(
                    text=corps,
                    source_uri=f"ohada://AUDCIF/article/{num or a.get('article_id')}",
                    schema="rag_erp",
                    tags=TAGS,
                    pii_policy=PIIRedactionPolicy.NONE,  # texte légal public
                    source_id=f"AUDCIF-art-{num}",
                    extra_metadata={
                        "acte": "AUDCIF",
                        "article_number": num,
                        "titre": (a.get("titre") or "").strip(),
                        "livre": a.get("livre"),
                        "chapitre": a.get("chapitre"),
                        "section": a.get("section"),
                        "licence": "CC-BY-4.0",
                        "source_dataset": REPO,
                    },
                    session=session,
                )
                total_chunks += n
                ingeres += 1
            await session.commit()
    finally:
        await engine.dispose()

    print(f"Terminé : {ingeres} articles traités, {total_chunks} chunks insérés dans rag_erp.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Ingestion AUDCIF → rag_erp")
    p.add_argument("--limit", type=int, default=0, help="limiter le nombre d'articles (0 = tous)")
    p.add_argument("--dry-run", action="store_true", help="afficher sans écrire en base")
    args = p.parse_args()
    asyncio.run(ingerer(args.limit or None, args.dry_run))
