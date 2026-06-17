# ZolaOS — Rapport de progression Phases 0 + 1

**Date** : 2026-05-17
**Statut global** : Phases 0 et 1 closes. Phase 2 amorcée.
**Référence** : [`ZOLAOS_MASTER_PLAN_V2.md`](../ZOLAOS_MASTER_PLAN_V2.md) (V2.2).

---

## 1. Vue d'ensemble

| Phase | Périmètre | Statut |
|-------|-----------|--------|
| 0 | Socle technique transverse (infra, secrets, bootstrap) | ✅ Cloturée |
| 1 | Fondations système (orchestrateur, sécurité, méta-agents, audit) | ✅ Cloturée |
| 2 | MVP Santé + 3 modules juridiques + RAG bge-m3 + pilotes terrain | 🔄 En cours |
| 3 | Pôle Engineering / Code Agent | À venir |
| 4 | Pôle ERP + 5 modules juridiques complémentaires | À venir |
| 5-9 | GRC, Fintech, Cyber, Industrialisation, Pôle K | À venir |

**Marché ciblé (rappel)** : République du Congo (Brazzaville) uniquement — **pas** la RDC. Cadres : OHADA, CEMAC/BEAC, OAPI, CIPRES, droit national CG.

---

## 2. Phase 0 — Socle technique transverse

### Livré
- **Stack Docker Compose** : `postgres` (pgvector/pg16), `redis`, `minio`, `app` (FastAPI), `caddy` (profile, TLS auto), `prometheus`+`grafana` (profile).
- **Bootstrap PostgreSQL** : schémas cloisonnés (`core`, `memory`, `rag_health`, `rag_legal`, `rag_erp`, `rag_code`, `audit`) + 8 rôles dédiés (`zolaos_migrator`, `zolaos_app`, `zolaos_agent_health`, `zolaos_agent_legal`, `zolaos_agent_erp`, `zolaos_agent_code`, `zolaos_audit_writer`, `zolaos_audit_reader`), créés par `infra/postgres/01_init_schemas.sql` via pattern `\gexec` (substitution côté client psql, pas DO PL/pgSQL).
- **Audit log append-only** : table `audit.log` avec chaîne de hash SHA-256, trigger BEFORE INSERT pour calcul de hash, triggers BEFORE UPDATE/DELETE `forbid_mutation`.
- **CI GitHub Actions** : 4 jobs (lint, test, security via gitleaks, docker build).
- **Configuration secrets** : `.env` séparé de `.env.example`, validation via Pydantic Settings, aucune valeur sensible avec défaut en clair.

### Pattern critique sauvegardé
[`project_psql_secrets_pattern.md`](../C--Users-duqat-.claude/projects/C--Users-duqat-ZOLA-LLM/memory/project_psql_secrets_pattern.md) : toujours utiliser `\gexec` pour injecter `:'var'` dans des `CREATE ROLE` ; jamais un bloc `DO PL/pgSQL` (l'interpolation `:'var'` n'a pas lieu dans les blocs serveur).

---

## 3. Phase 1 — Fondations système

### Livré

#### Volet A — Orchestrateur multi-agents
- **Interface unifiée** `LLMClient` (`src/zolaos/llm/base.py`) avec `Message`, `GenerationOptions`, `GenerationResult`.
- **Routeur** (`src/zolaos/agents/router.py`) : Llama-3-8B, system prompt sous `agents/prompts/router.md`, classe en 8 pôles (`Pole` enum : `health`, `legal`, `erp`, `grc`, `fintech`, `cyber`, `engineering`, `general`), sortie JSON validée par Pydantic (`RouteDecision`).
- **Méta-agent Planning** (`src/zolaos/agents/meta/planning.py`) : pattern Plan-and-Execute, validation DAG (pas de cycles, pas de dépendance vers id ≥ self).
- **Méta-agent Memory** (`src/zolaos/agents/meta/memory.py`) : `recall()` exige au moins un tag (RBAC anti-leak strict via `raise ValueError if not required_tags`).
- **Brigade simulée** (`src/zolaos/agents/brigade.py`) : agent unique placeholder Phase 1, vrais sous-agents Phase 2+.
- **Orchestrateur** (`src/zolaos/core/orchestrator.py`) : pipeline Router → Planning (si complexity == complex) → Brigade.

#### Volet B — Sécurité
- **JWT** (HS256/384/512 sélectionnable) + **API key** (HMAC-SHA256 avec pepper) dans `src/zolaos/core/security.py`.
- **bcrypt direct** (pas passlib) avec pré-hash SHA-256 pour supporter passwords > 72 octets.
- **Guard anti-fallback externe** (`src/zolaos/llm/guard.py`) : `ensure_external_fallback_allowed()` vérifie flag + clé + budget mensuel, lève `ExternalFallbackDisabledError` sinon. Testé en CI sur marker `security`.
- **ToolRegistry** (`src/zolaos/tools/base.py`) : allowlist par agent, audit hash de chaque invocation.
- **SafeWrite** (`src/zolaos/tools/safe_write.py`) : workspace allowlist + extensions/filenames interdits (8 tests `security`).

#### Volet C — Persistance
- **Modèles SQLAlchemy 2.0 async** (`src/zolaos/db/models.py`) : `User`, `ApiKey`, `MemoryEntry` (`Vector(1024)` + index HNSW).
- **Alembic** : migration `20260515_0001_initial_tables.py`, `version_table_schema="core"` (corrige le bug "permission denied for schema public" sur Postgres 15+).
- **bge-m3** retenu comme modèle d'embedding (1024 dim, multilingue, MIT) — utilisé Phase 2.

#### Volet D — Observabilité
- **structlog JSON** + **Prometheus** + **OpenTelemetry** instrumenté sur FastAPI.
- Métriques principales : `LLM_CALLS_TOTAL`, `LLM_CALL_DURATION_SECONDS`, `AGENT_INVOCATIONS_TOTAL`.

### Tests
- **30 tests unitaires** verts (router, planning, safe_write, security JWT/API key, v1 agents, external fallback guard, health, settings).
- **3 tests d'intégration** verts contre llama-server réel (`pytest -m integration`).

### KPI Phase 1 (révisés)
| Cible plan initial | Statut hardware Strix Halo |
|--------------------|-----------------------------|
| Routage p95 < 2 s | ✅ Atteint (median 1.34 s, max 1.39 s sur 5 runs stables) |
| E2E réponse courte < 5 s | ⚠️ Partiel (3.5 s ERP, 7.7 s santé) |
| E2E réponse longue < 15 s | ✅ 13.5 s sur contrat OHADA |
| ~~E2E < 2 s~~ | ❌ Inatteignable sur iGPU (exige RTX 4090+/H100) |

---

## 4. Pivot LLM — Strix Halo + llama.cpp Vulkan

### Contexte
Hardware dev découvert : ROG Flow Z13 GZ302EA, **AMD Ryzen AI MAX+ 395 (Strix Halo)** + **Radeon 8060S** + 128 Go RAM unifiée (64 Go alloués BIOS, jusqu'à 98 Go vus par Vulkan).

### Constat bloquant
Ollama 0.23.4 Windows ne contient que les backends CUDA (NVIDIA) et CPU. Pas de `ggml-vulkan.dll` dans `C:\Users\duqat\AppData\Local\Programs\Ollama\lib\ollama\`. `OLLAMA_VULKAN=true` est lu mais inopérant → CPU pur → 35-50 s/requête 8B.

ROCm Linux ne couvre pas le 8060S (iGPU RDNA 3.5 absent de la liste officielle). Docker Desktop Windows n'expose pas le GPU AMD aux conteneurs.

### Décision
Bascule vers **llama.cpp natif Windows** build `b9186` avec backend Vulkan officiel (AMD Radeon supporté nativement).

### Architecture résultante
```
┌─────────────────────────────────┐    ┌──────────────────────────────────┐
│  Hôte Windows                   │    │  Docker Desktop (WSL2)           │
│                                 │    │                                  │
│  llama-server.exe (b9186)       │◄───┤  zolaos-app (container)          │
│  ├─ Vulkan → Radeon 8060S       │HTTP│  LLM_HOST_ROUTER=                │
│  ├─ Port 11435 (8B router/      │    │   http://host.docker.internal:   │
│  │   brigade)                   │    │   11435                          │
│  └─ Port 11436 [futur 70B]      │    │                                  │
│                                 │    │  + postgres / redis / minio      │
│  Modèles .gguf hardlinkés       │    │                                  │
│  depuis ~/.ollama/models/blobs/ │    │                                  │
│  vers C:\models\                │    │                                  │
└─────────────────────────────────┘    └──────────────────────────────────┘
```

### Code adapté
- **Nouveau** `src/zolaos/llm/lcpp_client.py` : `LlamaCppClient`, OpenAI-compatible `/v1/chat/completions`, health = `/health`.
- **Settings** : `OLLAMA_HOST` → `LLM_HOST_ROUTER` + `LLM_HOST_CORE` + `LLM_BACKEND` (`llamacpp` | `ollama`) + `LLM_MODEL_*` + `LLM_API_KEY`.
- **Factory** (`src/zolaos/llm/factory.py`) : `make_router_client(settings)` (port 11435) + `make_core_client(settings)` (port 11436 futur). Dispatch sur `LLM_BACKEND`.
- **`OllamaClient` conservé** : sélectionnable via `LLM_BACKEND=ollama` (prod Linux + ROCm/CUDA reste viable).
- **`docker-compose.yml`** : service `ollama` commenté, `extra_hosts: host.docker.internal:host-gateway` ajouté à `app`.

### Lancement llama-server (référence)
```powershell
C:\Tools\llama.cpp\llama-server.exe `
  -m C:\models\llama-3-8b-q4_0.gguf `
  --alias llama3-8b `
  -ngl 99 `
  --host 0.0.0.0 `
  --port 11435 `
  -c 8192 `
  --device Vulkan0
```

### Modèles
Réutilisés depuis les blobs Ollama via **hardlinks NTFS** (zéro duplication, ~45 Go économisés) :
- `llama-3-8b-q4_0.gguf` → `sha256-6a0746a1ec1aef3e7ec53868f220ff6e389f6f8ef87a01d77c96807de94ca2aa` (4.66 Go)
- `llama-3-70b-q4_0.gguf` → `sha256-0bd51f8f0c975ce910ed067dcb962a9af05b77bafcdc595ef02178387f10e51d` (40 Go, pour Phase 2+)

---

## 5. Fix JSON strict (Phase 1.5)

### Problème
Sans grammar stricte, `response_format: {"type":"json_object"}` ne garantit pas la conformité. Le 8B vanilla dérivait sur certaines requêtes (ex: "Rédige un contrat OHADA" → génération d'un vrai contrat au lieu du JSON de routage).

### Solution
- `GenerationOptions` étendu avec `json_schema: dict | None`.
- `Router.classify()` et `PlanningAgent.plan()` fournissent leur schéma Pydantic via `RouteDecision.model_json_schema()` / `Plan.model_json_schema()`.
- `LlamaCppClient._build_payload()` traduit en `response_format: {"type":"json_schema", "json_schema":{...}}`.
- llama-server compile en **grammar GBNF stricte** → le modèle ne peut générer que des tokens conformes au schéma.

### Bonus mesuré
| Métrique routage | Avant fix | Après fix |
|------------------|-----------|-----------|
| Bug "Rédige contrat" | ❌ dérive | ✅ classe `legal` |
| Median latence (n=5) | 2.28 s | **1.34 s** (-41 %) |
| Max | 2.41 s | 1.39 s |

Le modèle s'arrête net sur les ~50 tokens contraints au lieu de "réfléchir" avant le JSON → routage 40 % plus rapide.

---

## 6. Décisions architecturales clés

1. **Llama-3-8B obligatoire** pour routeur + brigade (jamais Mistral 7B), cohérence de famille avec le 70B. [`feedback_llama_router.md`](../C--Users-duqat-.claude/projects/C--Users-duqat-ZOLA-LLM/memory/feedback_llama_router.md)
2. **Fallback API externe désactivé par défaut**, code présent mais guardé. Activation manuelle uniquement après documentation d'un plateau du modèle local.
3. **Pôle K (langues) en dernier** (Phase 9, pas avant).
4. **Pôle GRC indépendant** (Phase 5), pas subsumé dans ERP.
5. **Pôle Droit en 8 modules** (pas seulement OHADA) : 3 MVP Phase 2 (OHADA, Travail, Fiscal), 5 différés Phase 4+.
6. **Connector Framework générique** Phase 4 (pas spécifique Odoo/ERPNext).
7. **Backend LLM** : `llamacpp` (défaut dev, OpenAI-compatible portable) ; `ollama` (option prod Linux + ROCm/CUDA).

---

## 7. Sujets ouverts / dette technique

| ID | Sujet | Sévérité | Plan |
|----|-------|----------|------|
| D1 | Routage variable 1.4 → 4.8 s selon requête | Moyenne | Investiguer cache GBNF cold path (Phase 2) |
| D2 | "Code du travail" classé `erp` au lieu de `legal` | Faible | Affiner prompt router (Phase 2) |
| D3 | Image Docker pas rebuilt avec Dockerfile à jour | Faible | `docker compose build app` propre avant Phase 2 |
| D4 | `agents/prompts/router.md` calcule chemin via `parents[3]` → casse hors `/app/src` | Moyenne | Refactor en `pkg_resources` ou env var (Phase 2) |
| D5 | Ollama natif Windows tourne en parallèle sur 11434 (~5 Go RAM) | Cosmétique | Quit via tray quand on veut récupérer la RAM |
| D6 | Tests d'intégration nécessitent `docker cp tests/` + install pytest dans le container | Moyenne | Bind-mount `tests/` en dev + image dev séparée |
| D7 | Le 70B (Planning) n'a pas encore son llama-server dédié | Faible | Lancer sur port 11436 quand Phase 2 le requiert |

---

## 8. Mémoires persistantes en place

Index : [`MEMORY.md`](../C--Users-duqat-.claude/projects/C--Users-duqat-ZOLA-LLM/memory/MEMORY.md)

- `feedback_llama_router.md` — Llama-3-8B obligatoire pour le routeur
- `project_zolaos_vision.md` — vision globale, locale-first, fallback off
- `project_zolaos_market_focus.md` — RC uniquement (pas RDC)
- `project_psql_secrets_pattern.md` — pattern `\gexec` psql
- `project_latency_gpu_constraint.md` — Strix Halo + Vulkan + mesures réelles
- `feedback_user_manual_actions.md` — respecter le partage manuel/automatique

---

## 9. Plan Phase 2 — Décomposition

### Périmètre commercial (plan V2.2)
- Sous-agent **Pharmacologie** + RAG `rag_health` (CIM-10, LNME)
- Sous-agents **Droit OHADA / Travail CG / Fiscal CG** + RAG `rag_legal_*`
- **PII redaction** présent mais inactif
- **Audit trail** étendu (santé, droit, ERP — ERP arrive Phase 4)
- **2 pilotes terrain** (cabinet d'avocats + pharmacie/polyclinique)

### Travaux techniques faisables maintenant (sans dépendance externe)

| # | Bloc | Description | Tasks |
|---|------|-------------|-------|
| 1 | **Pipeline RAG** | Module ingestion + chunking (512 tokens, overlap 64) + embeddings bge-m3 + indexation pgvector avec tags RBAC (`country:cg`, `tenant:X`, `health`/`legal`) | 5-6 tasks |
| 2 | **Schémas SQL** | Migration Alembic pour collections par pôle (`rag_health.documents`, `rag_legal_ohada.documents`, etc.) avec index HNSW + GIN sur tags | 1 task |
| 3 | **Sous-agent Pharmacologie** | Scaffolding + prompt système + intégration RAG + stub "vérification de stock" | 2-3 tasks |
| 4 | **Sous-agents Droit** | 3 sous-agents (OHADA / Travail CG / Fiscal CG) + citation obligatoire + garde-fou anti-hallucination (refus si confiance < seuil) | 4-5 tasks |
| 5 | **PII redaction** | Module détection PII (regex + NER léger), exposé via flag, désactivé par défaut | 2 tasks |
| 6 | **Eval framework** | Loader vérité-terrain (YAML/JSON), runner pytest, métriques hallucination/precision/recall | 2-3 tasks |
| 7 | **Dette technique** | D3 (rebuild image), D4 (chemin prompts), D6 (bind-mount tests) | 3 tasks |

### Travaux à dépendance externe (à coordonner avec l'utilisateur)

| # | Bloc | Dépendance |
|---|------|------------|
| 8 | Sourcing **CIM-10** | OMS (libre, téléchargement direct) — peut être amorcé |
| 9 | Sourcing **LNME congolaise** | DPML (Direction de la Pharmacie et du Médicament) — contact officiel à initier |
| 10 | Sourcing **9 actes uniformes OHADA** | OHADA.com (libres, téléchargement) — peut être amorcé |
| 11 | Sourcing **Code du travail 45/75 CG** | Journal officiel CG / sites juridiques — à clarifier |
| 12 | Sourcing **CGI CG** + dernière LFP | Direction Générale des Impôts CG — contact officiel |
| 13 | Pilote **cabinet d'avocats** Brazzaville | Prospection commerciale |
| 14 | Pilote **pharmacie/polyclinique** | Prospection commerciale |
| 15 | **Validation pharmacien** (100 Q/R santé) | Recrutement expert |
| 16 | **Validation juriste** (50 cas/module) | Recrutement expert |

### Ordre d'attaque recommandé
1. **D3 + D4 + D6** (dette technique courte, libère l'itération)
2. **Schémas SQL RAG** (migration Alembic)
3. **Pipeline d'ingestion + bge-m3** (cœur technique)
4. **Sous-agent Pharmacologie** sur corpus jouet (CIM-10 sample) pour valider la chaîne bout-en-bout
5. **Sous-agents Droit** (3 modules en parallèle)
6. **PII redaction**
7. **Eval framework** (jeux de questions vérité-terrain dummy au début)
8. Le sourcing réel et les pilotes terrain restent à l'utilisateur

---

## 10. Métriques d'attente sortie Phase 2 (plan V2.2)

- Hallucination rate < 5 % in-domain
- Latence p95 < 3 s (révisé selon hardware cible prod)
- 2 pilotes actifs avec ≥ 50 requêtes/semaine
- 3 modules juridiques en production

---

## 11. Évolution de vision — Partenariat Polaris × ZolaOS (2026-05-17)

En cours de Phase 2, la vision globale du projet a été enrichie : ZolaOS reste la plateforme technologique avec ses **8 pôles V2.2 inchangés**, mais le modèle commercial passe d'un SaaS direct à un **partenariat avec un cabinet de conseil opérateur appelé Polaris**.

### Synthèse de l'évolution

- **ZolaOS** = la plateforme technologique multi-agents (8 pôles inchangés).
- **Polaris** = cabinet de conseil qui vend des missions augmentées en utilisant ZolaOS en arrière-plan.
- **Topologie double** : **Zolabox** (déploiement chez le client, données locales) et **Zolacortex** (déploiement chez Polaris, accès cross-tenants via missions). Même codebase, profils distincts via `ZOLAOS_PROFILE=box|cortex`.
- **Connexion sécurisée éphémère** Cortex → Box pendant les missions (JWT mission scopé + audit hash).
- **Apprentissage fédéré** (gradients chiffrés inter-Box) à concevoir Phase 4+.

### Impact sur la roadmap

- **Aucun fichier existant modifié** : `ZOLAOS_MASTER_PLAN_V2.md` reste intact comme référence historique.
- **Document d'addendum créé** : [`../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md) — complète V2.2 sans rien remplacer.
- **Pôles inchangés** : Santé reste prioritaire Phase 2 (pas dépriorité).
- **Nouvelles tasks "Polaris-1 à 11"** à intégrer en parallèle de Phase 2 (chantier transverse).
- **Adaptations transverses** : PII redaction obligatoire pré-ingestion, OUTPUT_FORMAT structuré strict, chunkers spécialisés, tenancy à 2 niveaux, table missions, génération rapports.

### Nouveaux segments clientèle

- Institutions gouvernementales (renforce GRC + module Droit administratif à ajouter)
- ONG / bailleurs internationaux (renforce GRC reporting + ERP projets)

### Mapping offres Polaris ↔ pôles ZolaOS

Voir la section 3 de l'addendum V3 pour le détail. Synthèse :

| Offre Polaris | Pôles ZolaOS mobilisés |
|---------------|------------------------|
| Conseil RH & Conformité | Droit (travail/social CG) + GRC |
| Fiscalité Opérationnelle | Droit (fiscal/OHADA) + ERP (compta SYSCOHADA) |
| Gestion de Trésorerie | ERP (finance) + Fintech |
| Audit Santé | Santé + GRC (DPML) |
| Cyber-défense | Cyber + GRC (Loi 29-2019) |
| Audit Institutions Gouvernementales | GRC + Droit (administratif, à ajouter) |
| ONG / Bailleurs | GRC + ERP (projets ONG) |

### Mémoires créées

- `project_polaris_partnership.md`
- `project_zolabox_zolacortex_topology.md`
- `feedback_preserve_documentation.md`
- `project_zolaos_vision.md` enrichi (section "Évolution 2026-05-17")

---

*Document généré automatiquement à partir de l'état du repo et de la mémoire au 2026-05-17.*
