# Assistant code souverain — runbook

Assistant de codage vendu aux **clients tech**, exécuté **sur la box du client**.
Proposition de valeur : *le code ne quitte jamais les murs du client* — pour les
entreprises qui ne peuvent/veulent pas envoyer leur code propriétaire à une API
externe (Claude Code, Copilot interdits pour souveraineté/IP). Le concurrent
n'est pas Claude Code (interdit chez ces clients) mais « rien ».

Profil **box uniquement** (absent en cortex). Le code du client = actif sensible
de la box, **jamais** répliqué sur le cortex Polaris (cf. `docs/…` Zero Trust).

## Architecture (patron `rag_tenant` appliqué au code)

| Pièce | Rôle |
|---|---|
| `rag_code` (`RagCodeDocument`, migration 0060) | index du code DU CLIENT, **cloisonné par tenant** (`tenant:<id>`, `source_uri=code://<tenant>/<path>`), schéma **sensible** (politique PII à l'ingestion) |
| `CodeAgent` (`agents/engineering/code.py`) | avant de générer, `retrieve(rag_code, tenant:<id>)` → injecte le contexte du dépôt ; dégradation douce si rien d'indexé |
| `CodeChunker` (`rag/chunking_specialized.py`) | découpe par frontières de symboles (fonctions/classes), fallback générique |
| `scripts/index_codebase.py` / `index_repo()` | indexe un dépôt → `rag_code` (bge-m3 + PII), incrémental |
| `agents/engineering/sandbox.py` | exécution de code en conteneur Docker jetable durci (optionnel) |

## Endpoints (`/v1/code/*`, profil box, identité requise)

- `POST /ask` — `{query, intent?, language_hint?, structured_output?}` → réponse ancrée sur le dépôt indexé. `repo_context: true/false` indique si des extraits ont ancré la réponse.
- `POST /index` — `{repo_dir, since?, reindex?}` → (ré)indexe le dépôt en **tâche de fond**. Le `tenant` est dérivé de l'identité authentifiée (jamais du body).
- `GET  /status` — nb d'extraits indexés pour ce tenant (le dépôt est-il prêt ?).
- `POST /run` — `{language, code, timeout_seconds?}` → exécute en sandbox. **403 si sandbox désactivée** (défaut).

## Prérequis de déploiement (box)

### 1. Modèle Qwen2.5-Coder-32B (obligatoire)
Servi **localement** sur la box, port `LLM_HOST_CODE` (défaut `:11436`), nom
`LLM_MODEL_CODE` (défaut `qwen2.5-coder-32b`). Dérogation assumée à la stack
Llama : ici la qualité du code EST la valeur vendue.
- **GPU requis** sur la box pour une latence utilisable (modèle 32B). Sans GPU,
  l'assistant est inexploitable → conditionne à quels clients on le vend.
- Servir via Ollama/llama.cpp comme le 8B/70B (3ᵉ processus).

### 2. Schéma `rag_code`
- Schéma + rôle `zolaos_code_agent` (écriture, indexation) : `infra/postgres/01_init_schemas.sql` (bootstrap) — déjà en place sur une base neuve.
- Table : `alembic upgrade head` (migration `20260728_0060`). Sur une base existante, créer le schéma en superutilisateur si le bootstrap n'a pas rejoué.
- Embeddings **bge-m3** requis (comme les autres corpus RAG).

### 3. Sandbox d'exécution (optionnelle, désactivée par défaut)
`CODE_SANDBOX_ENABLED=false` par défaut — capacité sensible, **activée
explicitement par le client**. Si activée :
- **Socket Docker** de la box monté dans le conteneur app + binaire `docker` accessible.
- Images tirées sur la box : `python:3.12-slim`, `node:20-slim`, `bash:5`.
- Réglages : `CODE_SANDBOX_TIMEOUT_SECONDS` (10), `CODE_SANDBOX_MEMORY` (256m), `CODE_SANDBOX_CPUS` (0.5), `CODE_SANDBOX_PIDS_LIMIT` (128), `CODE_SANDBOX_OUTPUT_MAX_BYTES` (64000).

Isolation d'un run : conteneur **jetable** `--network none`, non-root (65534),
rootfs **read-only** + tmpfs `/tmp`, `--cap-drop ALL`, `--security-opt
no-new-privileges`, limites mémoire/cpu/pids, timeout + kill, détruit après.
Code passé en **base64 via variable d'env** (aucune injection shell). **Aucun
accès** dépôt/DB/secrets/réseau → rayon de souffle = le conteneur jetable.

## Onboarding d'un client

```bash
# Indexation initiale du dépôt du client (sur la box), pour son tenant :
python scripts/index_codebase.py /chemin/vers/depot --tenant <tenant_id>

# Ré-indexation incrémentale (ex. hook post-commit ou tâche planifiée) :
python scripts/index_codebase.py /chemin/vers/depot --tenant <id> --since <git_ref>

# Réindexation complète (purge + reconstruction) :
python scripts/index_codebase.py /chemin/vers/depot --tenant <id> --reindex
```
L'indexation respecte `.gitignore` (via `git ls-files`), ignore secrets
(`.env`/`*.pem`/…) et binaires. Idempotente : un fichier inchangé (même
`content_sha`) est **sauté** (pas de ré-embedding). `--since` traite aussi les
**suppressions** (retire les lignes des fichiers supprimés). Ou déclencher via
`POST /v1/code/index`.

## Reste à durcir avant GA large

- **Sandbox** : l'option retenue (a) donne le socket Docker à l'app (flag off par
  défaut). Avant une GA large, migrer vers (b) un micro-service sandbox dédié qui
  ne partage jamais le socket avec l'app, ou (c) un runtime renforcé (gVisor/Kata).
- **Indexation à l'échelle** : la tâche de fond FastAPI suffit à petite échelle ;
  passer à une file de travaux réelle pour de gros dépôts / multi-tenants.
- **Overlay Polaris** `code_review`/`audit_securite_code` : repointés sur
  `rag_code` ; l'accès distant en mission passe par le tunnel box (JWT mission →
  `/v1/box/rag/search` schema=`rag_code`), à câbler pour l'audit sur dépôt indexé.
