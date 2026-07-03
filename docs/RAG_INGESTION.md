# Ingestion RAG — mode opératoire

**Objet** : procédure pour alimenter les bases de connaissance RAG de ZolaOS
(schémas `rag_legal`, `rag_erp`, `rag_health`, `rag_code`) — de la préparation
de l'image jusqu'à la vérification. Cas de référence : corpus **OHADA** (9 Actes
uniformes).
**Voir aussi** : `docs/DATA_KNOWLEDGE_ROADMAP.md` (sources par pôle),
`docs/ARCHITECTURE_TOPOLOGIE.md` (frontière LLM/données), `scripts/ingest_ohada.py`.

---

## 0. Principes (à garder en tête)

- **Le LLM ne « connaît » pas le Congo** : toute la connaissance locale vit dans
  les **données** (RAG + référence structurée), jamais dans les poids. Ingérer =
  charger de la donnée, pas réentraîner.
- **Déterministe d'abord** : les chiffres (barèmes, comptes) restent structurés
  (`ref/`), le RAG ne sert qu'à **citer / justifier** (garde-fous
  `requires_citation`, `min_confidence` dans `rag_agent.py`).
- **Rôle d'ingestion = `migrator`** (propriétaire des schémas `rag_*`). L'app
  (`zolaos_app`) n'a que le **SELECT** sur `rag_*` — zero-trust. L'ingestion est
  une opération d'**administration**, hors chemin applicatif.
- **Idempotent** : clé `(source_uri, chunk_index)` + `ON CONFLICT DO NOTHING`.
  Re-jouer une ingestion ne duplique rien.
- **PII** : politique explicite obligatoire sur schéma sensible. Texte légal
  public → `PIIRedactionPolicy.NONE`. Données client → `FISCAL`/`RH`/`MEDICAL`.
- **Licences** : tout corpus ingéré doit être tracé dans `NOTICE` +
  `THIRD_PARTY_LICENSES.md` (attribution CC-BY, etc.).

---

## 1. Prérequis — modèle d'embeddings bge-m3 baké dans l'image

L'ingestion et le retrieval calculent des vecteurs avec **`BAAI/bge-m3`** (1024d,
CPU). Le modèle (~2,3 Go) est **pré-embarqué au build** dans l'image `zolaos:dev`
(`Dockerfile` → `/opt/hf_cache`), pour un fonctionnement **hors-ligne** au runtime.

> ⚠️ Les téléchargements **anonymes** du Hub HuggingFace sont fortement **bridés**
> sur les gros fichiers (throttle serveur, ~0 débit après une rafale). Fournir un
> **`HF_TOKEN`** (même gratuit) rend le build fiable et rapide. Sans token et sans
> réseau non bridé, le build **bloque** sur le téléchargement du modèle.

```bash
# 1) Image de base zolaos:dev — bake bge-m3 (token recommandé)
HF_TOKEN=hf_xxx docker compose build app

# 2) Image de dev (pytest + hot-reload), hérite du modèle (FROM zolaos:dev)
docker compose -f docker-compose.yml -f docker-compose.dev.yml build app

# 3) Démarrer la stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d app
```

Vérifier que le modèle est bien présent dans l'image :
```bash
docker exec zolaos-app sh -c 'du -sh /opt/hf_cache; ls /opt/hf_cache/hub'
# → doit contenir models--BAAI--bge-m3 (~2,3 Go)
```

---

## 2. Migrations (schémas RAG + tables)

Les **schémas** (`rag_legal`, `rag_erp`, …) sont créés par le bootstrap
`infra/postgres/01_init_schemas.sql`. Les **tables** `documents` sont créées par
Alembic. S'assurer que la base est à jour :

```bash
docker exec zolaos-app alembic upgrade head
docker exec zolaos-postgres psql -U postgres -d zolaos -tAc \
  "SELECT to_regclass('rag_erp.documents'), to_regclass('rag_legal.documents');"
```

> Rappel : le rôle `migrator` doit avoir `search_path = core, public` (fixé par
> l'init) pour que les migrations non qualifiées atterrissent dans `core`.

---

## 3. Ingestion du corpus OHADA (cas de référence)

Source : dataset HuggingFace `Maathis-com/ohada-actes-uniformes` (**CC-BY-4.0**),
`nodes/articles.csv`. Script : `scripts/ingest_ohada.py`.

**Routage par acte** (chaque agent ne voit que ce qui le concerne, via les tags) :

| Acte | Schéma | Tag `module:` | Agent consommateur |
|---|---|---|---|
| **AUDCIF** (droit comptable, 120 art.) | `rag_erp` | `audcif` | Compta / pôle ERP |
| 8 autres actes (AUSCGIE, AUDCG, AUPC, AUS, AUPSRVE, AUSCOOP, AUA, AUCTMR — 3 006 art.) | `rag_legal` | `ohada` | agent juridique `ohada` |

```bash
# Aperçu sans écriture (compte + répartition par acte)
docker exec zolaos-app python scripts/ingest_ohada.py --dry-run

# Ingestion complète (les 9 actes)
docker exec zolaos-app python scripts/ingest_ohada.py

# Ou un acte précis
docker exec zolaos-app python scripts/ingest_ohada.py --actes AUDCIF
docker exec zolaos-app python scripts/ingest_ohada.py --actes AUSCGIE,AUDCG
```

> Le script ouvre sa propre session **migrator** (DSN async dérivé de
> `postgres_dsn_migrations`), lit le CSV, et appelle `ingest_text()` par article.
> Embedding CPU : compter quelques minutes pour l'AUDCIF, ~20-40 min pour les
> 3 006 articles restants (`AUSCGIE` seul en pèse 1 392).

---

## 3bis. Ingestion d'un document officiel (PDF / URL)

Pour les sources **hors HuggingFace** (textes officiels CG : CGI, Code du travail,
SYCEBNL, LNME…), utiliser `scripts/ingest_pdf.py` : il télécharge une URL (ou lit
un fichier local), extrait le texte (PDF via pypdf ; .docx/.html/.csv/.xlsx/.txt
aussi), découpe et ingère avec le rôle **migrator**. **Offline-first** : le modèle
bge-m3 baké est utilisé sans recheck réseau du Hub (`HF_HUB_OFFLINE` par défaut).

```bash
# Aperçu (télécharge + extrait + découpe, SANS base ni embeddings) — testable
# même sans le modèle complet (seul le tokenizer suffit) :
docker exec zolaos-app python /tmp/ingest_pdf.py \
  --url "https://www.sgg.cg/txts-droit-reg/OHADA-Acte-Uniforme-2022-entites-but-non-lucratif.pdf" \
  --schema rag_erp --source-id sycebnl_acte \
  --tags country:cg,module:projets_ong,type:texte_legal --dry-run

# Ingestion réelle (nécessite bge-m3 baké) :
docker exec zolaos-app python scripts/ingest_pdf.py \
  --file /tmp/cgi_cg.pdf --schema rag_legal --source-id cgi_cg \
  --tags country:cg,module:fiscal_cg,type:texte_legal
```

> Sources qualifiées (URL, format, licence) par domaine : voir `docs/sourcing/*.md`.

---

## 4. Vérification

```bash
# Comptes de chunks par schéma
for s in rag_legal rag_erp rag_health; do
  echo -n "$s: "; docker exec zolaos-postgres psql -U postgres -d zolaos -tAc \
    "SELECT count(*) FROM ${s}.documents;"
done

# Répartition par acte (métadonnées)
docker exec zolaos-postgres psql -U postgres -d zolaos -tAc \
  "SELECT extra_metadata->>'acte' AS acte, count(*) FROM rag_legal.documents GROUP BY 1 ORDER BY 1;"
```

**Test de récupération réel** (embeddings vrais, nécessite le modèle baké) — le
test d'intégration `tests/test_rag_erp.py` est **opt-in** :
```bash
docker exec -e ZOLAOS_RUN_RAG_INTEGRATION=1 zolaos-app \
  python -m pytest tests/test_rag_erp.py -o addopts="" -p no:cacheprovider -q
```

---

## 5. Ingérer un nouveau corpus (patron général)

Tout corpus texte s'ingère avec `zolaos.rag.ingest.ingest_text()` /
`ingest_file()`. Points obligatoires :

1. **Sourcer** + vérifier la **licence** → attribution `NOTICE` /
   `THIRD_PARTY_LICENSES.md`.
2. Choisir le **schéma** cible (`rag_legal`, `rag_erp`, `rag_health`, …) et les
   **tags** : toujours `country:<iso>` + `module:<m>` (les `default_tags` de
   l'agent RAG les exigent), plus `type:texte_legal|jurisprudence|doctrine`,
   `source:<origine>`.
3. **Politique PII** explicite (`NONE` pour public, sinon `FISCAL`/`RH`/`MEDICAL`).
4. Ingérer avec une **session `migrator`** (cf. `scripts/ingest_ohada.py` pour le
   patron : `create_async_engine(dsn_migrator)` + passage de `session=`).
5. **Vérifier** (comptes + retrieval) et, sur santé/droit/fiscal, faire **valider
   par un expert** avant mise en production.

> Le sous-agent consommateur se câble en déclarant `rag_schema`, `prompt_file` et
> `default_tags` (cf. `RAGAgent`) — aucune modification du moteur n'est requise
> pour ajouter de la connaissance.

---

## 6. Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| Build bloqué sur le téléchargement du modèle | Hub bridé (requêtes anonymes) | `HF_TOKEN=hf_xxx docker compose build app` |
| `permission denied for schema public` (migrations) | `search_path` du rôle non fixé | vérifier `ALTER ROLE ... SET search_path = core, public` (init) |
| `permission denied` à l'ingestion sur `rag_*` | session ouverte avec le rôle **app** | utiliser le rôle **migrator** (cf. script) |
| `retrieve` ne renvoie rien | corpus non ingéré, ou tags `country`/`module` absents | vérifier les comptes + les tags à l'ingestion |
| L'agent refuse de répondre | `requires_citation=True` + 0 match RAG | ingérer le corpus du module concerné |

---

*Mode opératoire établi le 2026-07-03. Le seul prérequis externe est un accès HF
(idéalement un `HF_TOKEN`) au moment du build pour peupler le cache du modèle.*
