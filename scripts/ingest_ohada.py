#!/usr/bin/env python
"""Ingestion du corpus OHADA (9 Actes Uniformes) dans les schémas RAG.

Source : dataset HuggingFace ``Maathis-com/ohada-actes-uniformes`` (licence
**CC-BY-4.0**), fichier ``nodes/articles.csv``. Chaque article devient un
document RAG ; ingestion **idempotente** (``source_uri`` unique +
``ON CONFLICT DO NOTHING``), donc ré-exécutable sans doublon.

Routage par acte (chaque agent ne voit que ce qui le concerne, via les tags) :
- **AUDCIF** (droit comptable) → schéma ``rag_erp``, tag ``module:audcif``
  (consommé par l'agent Compta / pôle ERP).
- **8 autres actes** → schéma ``rag_legal``, tag ``module:ohada``
  (consommé par l'agent juridique ``ohada`` dont les ``default_tags`` sont
  ``country:cg`` + ``module:ohada``).

Rôle d'ingestion = ``migrator`` (propriétaire des schémas ``rag_*``). L'app n'a
que le SELECT sur ``rag_*`` (zero-trust) : l'ingestion est une opération
d'administration, hors chemin applicatif.

Exécution (conteneur applicatif : HF + sentence-transformers + accès DB) :
    python scripts/ingest_ohada.py [--actes AUDCIF,AUSCGIE,...] [--limit N] [--dry-run]

Sans ``--actes``, les 9 Actes Uniformes sont ingérés. Le premier appel
télécharge le modèle d'embeddings ``BAAI/bge-m3`` (~2,3 Go).
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

# Routage par acte : acte_code -> (schéma RAG cible, tag module).
# Défaut (droit des affaires général) = rag_legal / module:ohada.
ROUTAGE_DEFAUT = ("rag_legal", "ohada")
ROUTAGE: dict[str, tuple[str, str]] = {
    "AUDCIF": ("rag_erp", "audcif"),  # droit comptable → pôle ERP/compta
}


def _router_acte(acte_code: str) -> tuple[str, str]:
    return ROUTAGE.get(acte_code, ROUTAGE_DEFAUT)


def charger_noms_actes() -> dict[str, str]:
    """acte_code -> full_name (pour l'entête et les métadonnées)."""
    path = hf_hub_download(REPO, "nodes/actes_uniformes.csv", repo_type="dataset")
    with open(path, encoding="utf-8") as f:
        return {r["acte_id"].strip(): (r.get("full_name") or "").strip() for r in csv.DictReader(f)}


def charger_articles(actes: set[str] | None) -> list[dict[str, str]]:
    """Articles du dataset, filtrés sur les actes demandés (tous si None)."""
    path = hf_hub_download(REPO, "nodes/articles.csv", repo_type="dataset")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if actes is None or (r.get("acte_code") or "").strip() in actes]


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire des schémas rag_*)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


def _corps_article(a: dict[str, str], nom_acte: str) -> tuple[str, str]:
    """Retourne (numero, texte complet à ingérer) — vide si pas de texte."""
    acte = (a.get("acte_code") or "").strip()
    num = (a.get("article_number") or "").strip()
    titre = (a.get("titre") or "").strip()
    text = (a.get("text") or "").strip()
    if not text:
        return num, ""
    entete = f"{acte} ({nom_acte}) — Article {num}" if nom_acte else f"{acte} — Article {num}"
    if titre:
        entete += f" — {titre}"
    return num, f"{entete}\n\n{text}"


async def ingerer(actes: set[str] | None, limit: int | None, dry_run: bool) -> None:
    settings = get_settings()
    noms = charger_noms_actes()
    articles = charger_articles(actes)
    if limit:
        articles = articles[:limit]

    # Répartition par schéma pour le récap.
    par_acte: dict[str, int] = {}
    for a in articles:
        par_acte[(a.get("acte_code") or "").strip()] = (
            par_acte.get((a.get("acte_code") or "").strip(), 0) + 1
        )
    print(f"OHADA : {len(articles)} articles à ingérer (dry_run={dry_run}).")
    for code, n in sorted(par_acte.items()):
        schema, module = _router_acte(code)
        print(f"  · {code:8s} {n:4d} art. → {schema} (module:{module})")

    if dry_run:
        return

    engine = create_async_engine(_dsn_async_migrator(settings), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    total_chunks = 0
    ingeres = 0
    try:
        async with sessionmaker() as session:
            for a in articles:
                acte = (a.get("acte_code") or "").strip()
                schema, module = _router_acte(acte)
                num, corps = _corps_article(a, noms.get(acte, ""))
                if not corps:
                    continue
                n = await ingest_text(
                    text=corps,
                    source_uri=f"ohada://{acte}/article/{num or a.get('article_id')}",
                    schema=schema,
                    tags=[
                        "country:cg",
                        "source:ohada",
                        "type:texte_legal",
                        f"acte:{acte}",
                        f"module:{module}",
                    ],
                    pii_policy=PIIRedactionPolicy.NONE,  # texte légal public
                    source_id=f"{acte}-art-{num}",
                    extra_metadata={
                        "acte": acte,
                        "acte_nom": noms.get(acte, ""),
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

    print(f"Terminé : {ingeres} articles traités, {total_chunks} chunks insérés.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Ingestion OHADA (9 Actes Uniformes) → rag_legal/rag_erp"
    )
    p.add_argument("--actes", default="", help="codes séparés par des virgules (défaut : tous)")
    p.add_argument("--limit", type=int, default=0, help="limiter le nombre d'articles (0 = tous)")
    p.add_argument("--dry-run", action="store_true", help="afficher la répartition sans écrire")
    args = p.parse_args()
    actes = {c.strip().upper() for c in args.actes.split(",") if c.strip()} or None
    asyncio.run(ingerer(actes, args.limit or None, args.dry_run))
