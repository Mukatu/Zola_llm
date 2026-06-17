# ZolaOS — Rapport de progression Phase 3 (Cortex→Box, Code Agent, Zero Trust)

**Date** : 2026-06-17
**Statut global** : Phase 3 **close côté code**. Connexion sécurisée éphémère Cortex→Box opérationnelle, premier sous-agent du Pôle Engineering livré, pivot stratégique IP acté (Zero Trust Client) et formalisé dans le code.
**Références** :
- Rapport Phase 0+1 : [`PHASE_1_REPORT.md`](./PHASE_1_REPORT.md)
- Rapport Phase 2 + 2 bis Polaris : [`PHASE_2_REPORT.md`](./PHASE_2_REPORT.md)
- Addendum Polaris : [`../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md) (annexes §11 Zero Trust, §12 Licence)

> Ce document **complète** `PHASE_2_REPORT.md` ; il ne le remplace pas. Les rapports antérieurs restent intacts comme snapshots historiques.

---

## 1. Vue d'ensemble

| Bloc | Périmètre | Statut |
|------|-----------|--------|
| **Connexion sécurisée éphémère Cortex → Box** | JWT mission (HS256), vérification triple, endpoints Box read-only, audit hash | ✅ |
| **Émission / vérification JWT mission** | `missions/tokens.py` : claims métier (`mid`/`cab`/`cli`/`off`/`scope`), TTL plafonné 6 h | ✅ |
| **`MissionClient` (Cortex)** | client httpx async read-only, profil cortex obligatoire | ✅ |
| **Endpoints Box** | `POST /v1/box/rag/search` (profil box only, scope ∩ tags, audit systématique) | ✅ |
| **Endpoints Cortex** | `POST /v1/cortex/missions`, `/revoke`, `GET /missions` (profil cortex only) | ✅ |
| **Audit Cortex→Box** | `missions/audit.py` : insertion `audit.log` chaîne hash inviolable côté client | ✅ |
| **Code Agent (Pôle Engineering)** | `agents/engineering/code.py` — generate/refactor/debug/explain/review/test | ✅ |
| **Pivot IP → Zero Trust Client** | abandon obfuscation/chiffrement, formalisé dans `MissionClient` + `PolarisOverlay` | ✅ |
| **Modèle de licence** | open-core AGPL v3 + overlays Polaris propriétaires + double licence commerciale | ✅ acté |
| **Tests** | +29 tests Phase 3 (missions, box, code agent, zero trust, IP guards) | ✅ |

---

## 2. Connexion sécurisée éphémère Cortex → Box

### Architecture (Polaris-8)

```
┌────────────────────────────┐       ┌────────────────────────────┐
│  ZOLAOS_PROFILE=cortex     │       │  ZOLAOS_PROFILE=box        │
│  (chez Polaris)            │       │  (chez le client)          │
│                            │       │                            │
│  MissionClient ────────────┼──HTTP──┤ POST /v1/box/rag/search    │
│   Authorization: Bearer    │  +JWT  │  _mission_claims()         │
│   <mission JWT>            │        │  → verify_mission_token()  │
│   (read-only RAG only)     │        │     1. signature HS256     │
│                            │        │     2. mission active DB   │
│                            │        │     3. expires_at > now()  │
│                            │        │  → scope_tags ∩ requested  │
│                            │        │  → retrieve() filtré tags  │
│                            │        │  → audit.log INSERT (hash) │
└────────────────────────────┘       └────────────────────────────┘
```

### JWT mission — `src/zolaos/missions/tokens.py`

- Claims : `sub` (consultant), `mid` (mission), `cab` (cabinet), `cli` (client), `off` (offre), `scope` (tags RBAC), `iat`/`exp`.
- **TTL effectif** = `min(demandé, plafond 6 h, mission.expires_at − now)`. Défaut 2 h.
- `issue_mission_token()` refuse une mission non `active` ou déjà expirée en DB.
- `verify_mission_token()` — **vérification triple** : signature JWT ✓ + mission existe et `status='active'` en DB ✓ + `expires_at > now()` ✓. Une mission `revoked_at IS NOT NULL` bloque immédiatement même si le JWT est encore dans sa fenêtre.

### Endpoints Box — `src/zolaos/api/v1/box.py`

- Router monté **uniquement en profil `box`** (`dependencies=[Depends(require_box)]`).
- `POST /v1/box/rag/search` : lecture seule, top-k cosine + filtre tags RBAC.
- **Intersection scope** : les `required_tags` doivent être un sous-ensemble de `scope_tags` du JWT, sinon `403 tags_outside_mission_scope`. Scope mission vide → `403`.
- Chaque requête → `audit_box_access()` (event `box_rag_search`, payload : query preview, tags effectifs, k, nombre de hits, similarité top-1).

### Endpoints Cortex — `src/zolaos/api/v1/cortex.py`

- Router monté **uniquement en profil `cortex`**.
- `POST /v1/cortex/missions` : crée la mission en DB + émet le JWT (auth Phase 1 ; le `Principal.tenant_uuid` doit être un tenant `cabinet` actif, sinon 403).
- `POST /v1/cortex/missions/{id}/revoke` : révocation immédiate (`status='revoked'`, `revoked_at=now`), 409 si déjà non active, 403 si la mission n'appartient pas au cabinet du principal.
- `GET /v1/cortex/missions` : liste des missions du cabinet (limite 200).
- Création et révocation journalisées dans `audit.log` (category `auth`, events `mission_created` / `mission_revoked`).

### Audit — `src/zolaos/missions/audit.py`

- Insertion SQL paramétrée dans `audit.log` ; les `payload_hash` / `prev_hash` / `row_hash` sont calculés par le trigger SQL côté DB (chaîne immuable, `forbid_mutation` interdit toute modification ultérieure).
- Payload minimal : `mission_id`, `cabinet_tenant_id`, `consultant_user_id`, `scope_tags`, `offre` + extras métier.

---

## 3. Code Agent — Pôle Engineering (V2.2 #25)

`src/zolaos/agents/engineering/code.py` — premier vrai sous-agent du Pôle Engineering.

- Intents : `generate`, `refactor`, `debug`, `explain`, `review`, `test`.
- Pattern **non-RAG** (le code est généré, pas récupéré d'un corpus) : pas de `requires_citation`, pas de `rag_schema`.
- Sortie libre par défaut ; `structured_output=True` impose un `CodeArtifact` JSON (`language`, `code`, `explanation`, `suggested_tests`, `warnings`) via grammar GBNF.
- **N'écrit jamais sur disque** : la persistance passe par `SafeWriteTool` (allowlist de workspaces).
- Disponible dans **les deux profils** (box et cortex).
- **Modèle** : `LLM_MODEL_BRIGADE` (Llama-3-8B) par défaut pour la latence ; surchargeable via `force_model` (ex. Llama-3-70B `LLM_MODEL_CORE` pour les gros projets). Voir §6.
- À venir Phase 3.2 : exécution de code en sandbox Docker éphémère (non livré).

---

## 4. Pivot stratégique IP — Zero Trust Client (acté 2026-05-18)

### Décision

La stratégie initiale de protection IP (obfuscation Cython/Nuitka, chiffrement modèles, TEE) est **abandonnée**. Constat : on ne peut pas réellement protéger des actifs qu'on livre (reverse engineering assisté par IA en 2026, extraction de prompt LLM par l'inférence). **Conclusion : on ne livre pas les actifs sensibles.**

### Principe

Les actifs sensibles ne sont **jamais déployés chez le client**. La Zolabox ne contient que des actifs publics V2.2 (sous-agents génératifs à prompts publics, pipeline RAG + données client, Llama-3-8B générique). **Aucun** overlay Polaris, prompt cabinet, modèle fine-tuné Congo ni template `.docx` cabinet ne quitte le hardware Polaris.

### Formalisation dans le code

- `MissionClient` (`missions/client.py`) est **strictement read-only sur le RAG** : jamais de proxy d'inférence LLM via la Box, jamais d'écriture distante. Docstring contractuelle explicite.
- `PolarisOverlay` (`agents/polaris/_base.py`) : l'inférence (qui voit le prompt cabinet en clair) se fait **toujours** sur le `client` LLM local Cortex ; le `mission_client` ne sert qu'à récupérer des chunks RAG anonymisés depuis la Box distante. Le prompt cabinet **ne traverse jamais le réseau** vers la Box.

### Flux d'une mission d'audit (résumé)

1. Consultant crée la mission (Cortex) → JWT 1-3 h, `scope_tags` défini.
2. Overlay Polaris instancié **chez Polaris** (profil cortex).
3. `MissionClient.rag_search()` → `/v1/box/rag/search` : JWT vérifié, scope intersecté, `retrieve()` local renvoie des chunks **déjà anonymisés** (PII redaction pré-ingestion), audit hash chez le client.
4. La Box renvoie uniquement les chunks anonymisés.
5. Le Cortex reconstruit le prompt complet (prompt secret cabinet + chunks + question), appelle son llama-server **local**, produit le JSON OUTPUT_FORMAT, génère le `.docx`.
6. Mission terminée → JWT expire → accès Box coupé.

### Impact tasks IP (#70-76)

| Task | Statut |
|------|--------|
| #70 garde-fou applicatif prompts cabinet | ✅ conservé (défense en profondeur) |
| #71 strip box au build | ✅ **central** à l'archi Zero Trust |
| #72 obfuscation Nuitka | ⏳ conservée sur code générique restant (optionnel) |
| #73 chiffrement modèles + licence en ligne | ❌ **fermée** (obsolète) |
| #74 TEE (SGX/SEV-SNP) | ❌ **fermée** (obsolète) |
| #75 formalisation Zero Trust dans le code | ✅ fait (`MissionClient` + `PolarisOverlay`) |
| #76 test E2E flux Zero Trust | ✅ fait (`tests/test_zero_trust_flow.py`) |

Référence : `project_zero_trust_client_architecture.md`, `project_ip_protection_strategy.md`.

---

## 5. Modèle de licence (acté 2026-05-19)

**Open-core** :
- **Cœur public ZolaOS** sous **AGPL v3 ou ultérieure** (`SPDX-License-Identifier: AGPL-3.0-or-later`) — clause "use over network" §13 protège contre le fork commercial fermé, cohérent avec souveraineté/auditabilité (code livré = code lisible 100 %).
- **Composants propriétaires Polaris** (overlays, prompts secrets, templates `.docx`, modèles fine-tunés Congo) **non distribués** (secret des affaires, protégé par l'archi Zero Trust → clause AGPL non concernée).
- **Double licence commerciale** négociable (`licensing@polaris.cg`).

Fichiers : `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md` (racine).

---

## 6. État du modèle LLM — **Llama-3 conservé** (rappel et confirmation)

Décision **maintenue** : ZolaOS reste sur **Llama-3 (8B + 70B)** pour routeur, brigade, sous-agents et Code Agent — cohérence de famille, pas de bascule de framework.

| Rôle | Setting | Modèle |
|------|---------|--------|
| Routeur | `LLM_MODEL_ROUTER` | `llama-3-8b` |
| Brigade / sous-agents / Code Agent | `LLM_MODEL_BRIGADE` | `llama-3-8b` |
| Planning (méta-agent lourd) | `LLM_MODEL_CORE` | `llama-3-70b` |

- Le code applicatif (`core/settings.py`, `agents/engineering/code.py`) **n'utilise que ces valeurs Llama**. Aucune référence à un autre modèle n'est câblée.
- Les fichiers `Modelfile` / `Modelefile.txt` à la racine référencent `qwen3-coder-next` : ce sont des **artefacts d'expérimentation Ollama isolés, non reliés au code** et **sans effet** sur le runtime. Ils sont conservés en l'état (à ignorer) mais ne traduisent **aucun** changement de doctrine modèle.
- Attribution **"Built with Llama"** obligatoire dans la doc/UI client. Tout modèle fine-tuné Congo (Phase 5+) reste sous Llama 3 Community License.

Référence : `feedback_llama_router.md`, `project_licensing_model.md`.

---

## 7. Tests Phase 3

| Suite | Tests | Couverture |
|-------|-------|------------|
| `tests/test_mission_token_and_box.py` | 9 | émission/vérification JWT, TTL plafonné, endpoint box, intersection scope, audit |
| `tests/test_cortex_missions.py` | 6 | création/révocation/listing missions, garde-fous tenant cabinet |
| `tests/test_code_agent.py` | 6 | intents, structured output, parsing `CodeArtifact`, no-disk-write |
| `tests/test_zero_trust_flow.py` | 3 | flux E2E Cortex→Box, prompt cabinet ne transite pas |
| `tests/test_ip_protection_guards.py` | 5 | guards profil, MissionClient read-only, overlay cortex-only |
| `tests/test_polaris_remote_overlay.py` | 2 | overlay via `mission_client` distant |

**Run vérifié le 2026-06-17** (image `zolaos:dev-test`, Python 3.12) : **117 tests collectés → 114 passés, 0 échec, 3 désélectionnés** (marqueurs `integration` + `eval`, nécessitent Postgres/Redis/LLM réel et ne sont pas lancés hors stack complète). Couverture cumulée Phase 1 → Phase 4 (overlays Phase 4 : voir [`PHASE_4_REPORT.md`](./PHASE_4_REPORT.md)).

> Note build : l'image de base avait une couche `pip install` figée en cache antérieure à l'ajout des libs d'ingestion documentaire ; un rebuild `--no-cache` a été nécessaire pour embarquer `python-docx` / `openpyxl` / `pypdf` (présents dans `pyproject.toml`). Pensez à `docker compose build --no-cache app` après toute évolution des dépendances.

---

## 8. Dette technique / sujets ouverts

| ID | Sujet | Sévérité | Plan |
|----|-------|----------|------|
| D7 | llama-server 70B (Planning + Code Agent gros projets) pas encore lancé en dédié | Faible | Lancer sur port 11435 quand requis |
| P3.1 | Sandbox d'exécution Code Agent | Moyenne | Phase 3.2 (Docker éphémère) |
| P3.2 | `MissionClient` sans retry/backoff structuré | Faible | À durcir si latence réseau réelle problématique |

---

*Document généré à partir de l'état du repo et de la mémoire au 2026-06-17.*
