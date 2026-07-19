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
import unicodedata

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


def _fusionner_doublons(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Fusionne les lignes du CSV dupliquées pour un même (acte_code, article_number).

    Le dataset source contient, pour ~40% des articles, plusieurs lignes portant
    le même ``article_number`` (OCR d'un PDF à mise en page 2 colonnes, souvent
    scindé en fragments mal recollés) — parfois un texte tronqué (« stub ») à
    côté du texte complet, parfois deux fragments distincts et non redondants.

    Sans fusion, ``ingest_text`` reçoit une ligne par doublon avec le **même**
    ``source_uri``/``source_id`` : la 2e insertion est silencieusement ignorée
    par ``ON CONFLICT DO NOTHING`` (contrainte ``source_uri``+``chunk_index``).
    Le contenu effectivement conservé dépend alors de l'ORDRE arbitraire du CSV
    — ex. constaté : AUSCGIE Article 13 (« mentions obligatoires des statuts »,
    la disposition générale qui s'applique notamment à la SARL) ne conservait
    que le stub « Les statuts mentionnent : », la liste des 11 mentions étant
    perdue — ce qui l'empêchait de remonter au retrieval face à un article
    concurrent (ex. AUSCOOP) resté complet.

    Stratégie (ne perd jamais de contenu, déterministe) :
    - textes strictement identiques → dédupliqués ;
    - un texte qui n'est qu'un préfixe d'un autre (stub tronqué) → écarté au
      profit de la version la plus longue ;
    - fragments distincts restants → concaténés (ordre du CSV), le chunker
      générique se chargera de les redécouper si le total dépasse la fenêtre.
    """
    groupes: dict[tuple[str, str], list[dict[str, str]]] = {}
    ordre: list[tuple[str, str]] = []
    for r in rows:
        cle = ((r.get("acte_code") or "").strip(), (r.get("article_number") or "").strip())
        if cle not in groupes:
            groupes[cle] = []
            ordre.append(cle)
        groupes[cle].append(r)

    fusionnes: list[dict[str, str]] = []
    for cle in ordre:
        lignes = groupes[cle]
        if len(lignes) == 1:
            fusionnes.append(lignes[0])
            continue
        textes: list[str] = []
        for ligne in lignes:
            t = (ligne.get("text") or "").strip()
            if not t or any(t == vu or vu.startswith(t) for vu in textes):
                continue
            textes = [vu for vu in textes if not t.startswith(vu)]
            textes.append(t)
        base = dict(lignes[0])
        base["text"] = "\n\n".join(textes)
        fusionnes.append(base)
    return fusionnes


def charger_articles(actes: set[str] | None) -> list[dict[str, str]]:
    """Articles du dataset, filtrés sur les actes demandés (tous si None).

    Les doublons (même acte_code + article_number) sont fusionnés — voir
    ``_fusionner_doublons`` — avant retour, pour ne jamais ingérer un article
    tronqué à cause de l'ordre du CSV.
    """
    path = hf_hub_download(REPO, "nodes/articles.csv", repo_type="dataset")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if actes is None or (r.get("acte_code") or "").strip() in actes]
    return _fusionner_doublons(rows)


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire des schémas rag_*)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


# Détection de forme juridique par mot-clé (texte OCR sans accents, ex. "societe
# a responsabilite limitee") → (label canonique accentué + sigle, tag).
#
# Contexte : le texte brut des articles AUSCGIE (et d'autres actes) est issu
# d'un OCR de mauvaise qualité (accents perdus, mots recomposés — "Ie" pour
# "le", etc.), alors que d'autres actes du même dataset (ex. AUSCOOP) ont un
# texte propre et bien accentué. Résultat mesuré : à qualité de contenu égale,
# un article AUSCGIE pertinent (ex. dispositions SARL) perd le retrieval
# hybride (lexical+vecteur) face à un article d'un autre acte truffé des mêmes
# mots-clés de requête mais bien orthographiés. On compense en injectant, pour
# les articles qui mentionnent une forme sociale, la graphie canonique
# accentuée + le sigle usuel — ce qui redonne un signal lexical exploitable
# sans toucher au moteur de retrieval ni au chunker générique.
_FORMES_JURIDIQUES: list[tuple[str, str, str]] = [
    ("responsabilite limitee", "société à responsabilité limitée (SARL)", "sarl"),
    ("societe anonyme", "société anonyme (SA)", "sa"),
    ("nom collectif", "société en nom collectif (SNC)", "snc"),
    ("commandite simple", "société en commandite simple (SCS)", "scs"),
    ("commandite par actions", "société en commandite par actions (SCA)", "sca"),
    ("actions simplifiee", "société par actions simplifiée (SAS)", "sas"),
    ("societe en participation", "société en participation", "societe_participation"),
    ("interet economique", "groupement d'intérêt économique (GIE)", "gie"),
    # AUSCOOP (Acte uniforme relatif au droit des sociétés coopératives) : ce
    # texte-là est propre et bien accentué ("société coopérative") plutôt
    # qu'issu d'un OCR dégradé — voir `_sans_accents` ci-dessous, qui neutralise
    # la différence pour que ce même needle ASCII matche les deux graphies.
    ("cooperative", "société coopérative", "cooperative"),
]


def _sans_accents(text: str) -> str:
    """Retire les diacritiques (ex. "coopérative" -> "cooperative") pour un matching robuste
    aux deux graphies possibles du corpus (OCR sans accents vs texte propre accentué)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _formes_detectees(text: str) -> list[tuple[str, str]]:
    """Formes juridiques (label, tag) mentionnées dans `text` (insensible à la casse et aux accents)."""
    hay = _sans_accents(text.lower())
    return [(label, tag) for needle, label, tag in _FORMES_JURIDIQUES if needle in hay]


def _corps_article(a: dict[str, str], nom_acte: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Retourne (numero, texte complet à ingérer, formes juridiques détectées).

    Le texte complet inclut, le cas échéant, une ligne de renvoi terminologique
    listant les formes sociales mentionnées (graphie canonique + sigle) — voir
    `_FORMES_JURIDIQUES`.
    """
    acte = (a.get("acte_code") or "").strip()
    num = (a.get("article_number") or "").strip()
    titre = (a.get("titre") or "").strip()
    text = (a.get("text") or "").strip()
    if not text:
        return num, "", []
    entete = f"{acte} ({nom_acte}) — Article {num}" if nom_acte else f"{acte} — Article {num}"
    if titre:
        entete += f" — {titre}"
    formes = _formes_detectees(text)
    corps = f"{entete}\n\n{text}"
    if formes:
        corps += "\n\n(Renvoi terminologique — formes sociales visées : " + ", ".join(
            label for label, _tag in formes
        ) + ".)"
    return num, corps, formes


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
                num, corps, formes = _corps_article(a, noms.get(acte, ""))
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
                        *(f"forme:{tag}" for _label, tag in formes),
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
