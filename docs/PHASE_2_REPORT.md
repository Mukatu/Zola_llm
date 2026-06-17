# ZolaOS — Rapport de progression Phase 2 + Phase 2 bis Polaris

**Date** : 2026-05-17
**Statut global** : Phase 2 (MVP technique) + Phase 2 bis (overlays Polaris) **closes côté code**. Prête à recevoir des corpus réels et démarrer les pilotes terrain.
**Références** :
- Plan originel : [`ZOLAOS_MASTER_PLAN_V2.md`](../ZOLAOS_MASTER_PLAN_V2.md) (intact, snapshot historique)
- Addendum Polaris : [`ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md)
- Rapport Phase 0+1 : [`PHASE_1_REPORT.md`](./PHASE_1_REPORT.md) (intact)

> Ce document **complète** `PHASE_1_REPORT.md` ; il ne le remplace pas. Les fondations Phase 0/1 restent telles quelles, on y ajoute ici tout ce qui a été produit pour Phase 2 (MVP commercial Santé + Droit + ERP) et la couche Polaris (Zolabox/Zolacortex, overlays, rapports `.docx`).

---

## 1. Vue d'ensemble

| Bloc | Périmètre | Statut |
|------|-----------|--------|
| **Infra RAG** | embeddings bge-m3, chunking générique + 4 chunkers spécialisés, loaders 7 formats, ingestion idempotente, retrieval cosine + RBAC tags | ✅ |
| **Sous-agents génératifs V2.2** | classe abstraite `RAGAgent` + 4 sous-agents (Pharma, OHADA, Travail CG, Fiscal CG) + 4 prompts versionnés | ✅ |
| **PII redaction** | module `security/pii.py` avec 5 politiques (NONE/GENERIC/FISCAL/RH/MEDICAL), hash stable tiers, tranches salaires, **garde-fou bloquant** sur schémas sensibles | ✅ |
| **Eval framework** | datasets YAML vérité-terrain, 6 métriques par cas, agrégation `DatasetReport`, runner CLI, marker pytest `eval` | ✅ |
| **Profil Box/Cortex** | `ZOLAOS_PROFILE` + module `core/profiles.py` (décorateurs sync/async + dépendances FastAPI) | ✅ |
| **Overlays Polaris** | classe `PolarisOverlay`, 3 schémas `OUTPUT_FORMAT` (RH/Fiscal/Trésorerie), 3 overlays, 3 prompts secrets cabinet | ✅ |
| **Reports `.docx`** | moteur Jinja2 + python-docx, 2 templates conformes specs Polaris (Fiscal Audit, RH Audit) | ✅ |
| **Tenancy 2 niveaux + missions** | `core.tenants` (cabinet ⇋ client) + `core.missions` (JWT scope éphémère) | ✅ |
| **Router enrichi** | champ `module` obligatoire pour dispatch fin (9 modules `legal`, 3 `health`, 5 `erp`…) | ✅ |
| **Tests** | 30 + 3 (Phase 1) + 11 Polaris + 8 eval framework = **52 verts** | ✅ |

---

## 2. Pipeline RAG (Phase 2 cœur)

### Modules livrés

| Module | Fichier | Description |
|--------|---------|-------------|
| Embeddings | `src/zolaos/rag/embeddings.py` | `EmbeddingService` bge-m3 (1024 dim, multilingue MIT), batching, wrapper `aencode_one` / `aencode` async |
| Chunking générique | `src/zolaos/rag/chunking.py` | Sliding window tokens (512 cible, 64 overlap) via tokenizer bge-m3 |
| Chunkers spécialisés | `src/zolaos/rag/chunking_specialized.py` | `AccountingChunker` (écritures comptables), `LegalClauseChunker` (contrats), `LegalArticleChunker` (CGI/OHADA), `MedicalCaseChunker` (dossiers patients) + fallback automatique |
| Loaders | `src/zolaos/rag/ingest._load_text` | 7 formats : TXT, MD, PDF, CSV, **XLSX** (Grand Livre), **DOCX** (contrats), HTML |
| Ingestion | `src/zolaos/rag/ingest.py` | `ingest_text()` / `ingest_file()` idempotents (`ON CONFLICT DO NOTHING` sur source_uri+chunk_index), **PII hook bloquant** intégré |
| Retrieval | `src/zolaos/rag/retrieval.py` | Top-k cosine `<=>` + filtre tags RBAC `@>` (anti-leak strict) |

### Schémas SQL (migration 20260517_0002)

- `rag_health.documents` (CIM-10, LNME, dossiers santé)
- `rag_legal.documents` (OHADA, Travail CG, Fiscal CG, Social CG, …)

Indexation par table :
- **HNSW** sur `embedding` (`vector_cosine_ops`, m=16, ef=64)
- **GIN** sur `tags` (filtre RBAC rapide)
- **GIN** sur `extra_metadata` (filtres ad-hoc)
- **UNIQUE** sur `(source_uri, chunk_index)` (idempotence)

Permissions cascadées : `zolaos_app` + `zolaos_<pole>_agent` ont `SELECT`, `zolaos_migrator` propriétaire.

---

## 3. Sous-agents génératifs V2.2

### Classe abstraite réutilisable

`src/zolaos/agents/rag_agent.py` :
- `RAGAgent` : pattern `retrieve → contexte numéroté → LLM → réponse + citations`
- `InsufficientContextError` : refus structuré si `requires_citation=True` et pas de match
- `min_confidence` : refus si similarité top-1 < seuil (santé 0.50 / droit 0.55)

### 4 sous-agents concrets

| Agent | Schéma RAG | Tags par défaut | Modèle |
|-------|------------|------------------|--------|
| `PharmacologyAgent` | `rag_health` | `country:cg, module:pharmacology` | `llama3-8b` |
| `OhadaAgent` | `rag_legal` | `country:cg, module:ohada` | `llama3-8b` |
| `TravailCgAgent` | `rag_legal` | `country:cg, module:travail_cg` | `llama3-8b` |
| `FiscalCgAgent` | `rag_legal` | `country:cg, module:fiscal_cg` | `llama3-8b` |

### Prompts versionnés

`agents/prompts/health/pharmacology.md`, `agents/prompts/legal/{ohada,travail_cg,fiscal_cg}.md` — frontmatter YAML versionné (`version`, `last_review`, `reviewer`, `test_set`), périmètre explicite, règles strictes, formats de réponse types, garde-fous.

### Garantie capacités V2.2 préservées

- ✅ Réponses **génératives libres** par défaut (pas de schéma JSON imposé sur les sous-agents génériques)
- ✅ Disponibles dans **les deux profils** (Box et Cortex)
- ✅ `requires_citation=True` empêche l'hallucination ; aucune contrainte de format ailleurs

---

## 4. PII redaction (prérequis bloquant)

### Module `src/zolaos/security/pii.py`

5 politiques :
- `NONE` : passthrough (corpus public : OHADA, CIM-10, CGI officiel)
- `GENERIC` : masque email/téléphone/IBAN/carte/CNSS
- `FISCAL` : hash stable tiers (`FR_xxxxx`), montants conservés
- `RH` : noms/IDs masqués, salaires → tranches (`[1M-2.5M FCFA]`)
- `MEDICAL` : identité patient masquée, **pathologies + posologies conservées**

Détecteurs : téléphone CG (+242 04/05/06), email, IBAN, carte bancaire, CNSS, montants FCFA, noms (Title Case heuristique + stop-list).

### Hook bloquant intégré à l'ingestion

`require_policy_for_ingest()` : `ingest_text()` / `ingest_file()` exigent désormais un argument `pii_policy: PIIRedactionPolicy | None` **explicite**. Sans politique sur un schéma sensible (`rag_health`, `rag_legal`, `rag_erp`) → `ValueError` claire qui force le choix conscient.

### Stats trace

Chaque chunk indexé porte dans `extra_metadata` :
```json
{"pii_policy": "fiscal", "pii_stats": {"emails": 1, "phones": 1, "tiers_hashed": 2, ...}}
```

→ Audit facilité, possibilité de re-traiter un corpus avec une politique plus stricte si besoin.

---

## 5. Eval framework

### Modules

| Module | Rôle |
|--------|------|
| `src/zolaos/eval/dataset.py` | Loader YAML + validation Pydantic (`EvalDataset`, `EvalCase`, `ExpectedCitation`) |
| `src/zolaos/eval/metrics.py` | `evaluate_case()`, `CaseReport`, `DatasetReport` (pass rate, p50/p95, hallucination rate, breakdown par sévérité) |
| `src/zolaos/eval/runner.py` | `run_dataset()` async + CLI `python -m zolaos.eval.runner <dataset.yaml>` |

### Métriques calculées

Par cas :
- `passed` (bool global)
- `expected_kw_hit_rate` (mots-clés attendus présents)
- `forbidden_kw_hit` (mots interdits — échec critique)
- `citation_precision` / `citation_recall` (sources attendues couvertes)
- `refusal_correct` (si `must_refuse=true` honoré)
- `latency_seconds`
- `failure_reasons[]`

Agrégées : pass rate global, p50/p95 latence, hallucination rate, breakdown par sévérité (critical/high/medium/low).

### Marker pytest

`pytest -m eval` (à utiliser pour les tests d'évaluation contre LLM réel une fois les corpus ingérés).

---

## 6. Topologie Polaris — Profil Box/Cortex

### Settings

`Settings.ZOLAOS_PROFILE: Literal["box", "cortex"] = "box"` (défaut sûr).

### Module `src/zolaos/core/profiles.py`

- `Profile` enum (`BOX`, `CORTEX`)
- `current_profile()` + `require_profile(*allowed)`
- Décorateurs `@cortex_only` / `@box_only` (gèrent sync ET async transparemment)
- Dépendances FastAPI `require_cortex()` / `require_box()`

### Garantie testée

- Tout overlay Polaris en profil `box` → `ProfileError`
- `build_report()` en profil `box` → `ProfileError`
- Sous-agents V2.2 disponibles dans les 2 profils sans modification

---

## 7. Overlays Polaris (Cortex uniquement)

### Classe abstraite

`src/zolaos/agents/polaris/_base.py` :
- `PolarisOverlay(RAGAgent)` : vérifie profil Cortex à l'init, force `response_schema` obligatoire, `requires_citation=True`

### Schémas OUTPUT_FORMAT (conformes specs `.docx` Polaris)

`src/zolaos/agents/polaris/schemas.py` :

| Schéma | Champs obligatoires (spec Polaris) |
|--------|--------------------------------------|
| `RhAuditFinding` | `clause_ou_situation` / `risque_prudhommal` / `reference_legale` / `note_securisation` (+ severite, remediation optionnelle) |
| `FiscalAuditFinding` | `description_risque` / `reference_legale` / `impact_financier_fcfa` / `action_corrective` (+ severite) |
| `TresorerieFinding` | `risque_tresorerie` / `impact_fcfa` / `recommandation` / `calendrier_action` (+ severite — provisoire) |

Bundles : `RhAuditOutput` / `FiscalAuditOutput` / `TresorerieAuditOutput` contiennent `synthese` + liste de findings + extras (gains, cash_flow_recommendations…).

### 3 overlays livrés

| Overlay | Nom officiel | Sous-agents génériques utilisés |
|---------|--------------|----------------------------------|
| `ConformiteRhOverlay` | `ZolaCortex-Conformite-RH` | `legal.travail_cg` |
| `FiscalOhadaOverlay` | `ZolaCortex-Fiscal-OHADA` | `legal.ohada` + `legal.fiscal_cg` |
| `TresorerieOverlay` | `ZolaCortex-Tresorerie` | `erp.finance` (à créer Phase 4) — provisoire |

### Prompts secrets cabinet

`agents/prompts/polaris/{conformite_rh,fiscal_ohada,tresorerie}.md` — frontmatter `secret: true`, méthodologies Polaris (3 étapes), formats JSON stricts imposés.

---

## 8. Module `reports/`

### Moteur

`src/zolaos/reports/builder.py` :
- `build_report(template, output_path, context)` `@cortex_only`
- Pipeline : Jinja2 (templates `.md.j2`) → Markdown structuré → python-docx
- Mini-parseur : titres (`#`, `##`, `###`), listes à puces, tableaux pipe `| col | col |`

### 2 templates conformes specs `.docx` Polaris

| Template | Contenu |
|----------|---------|
| `fiscal_audit.md.j2` | Synthèse Exécutive + tableau gains immédiats + tableau risques classés par sévérité + recommandations cash-flow + limitations |
| `rh_audit.md.j2` | Matrice de Vulnérabilité Contractuelle (tableau) + Fiches de Remédiation Légale (par finding) + Protocole de Clôture de Risque + limitations |

### Vérifié bout-en-bout

Test `test_build_fiscal_report_end_to_end` : passe un `FiscalAuditOutput` peuplé → fichier `.docx` réel généré → relecture python-docx valide la présence du titre. Idem pour RH.

---

## 9. Tenancy 2 niveaux + missions

### Migration 20260517_0003

- `core.tenants` (id, name, **tenant_type IN ('cabinet','client')**, parent_tenant_id (FK self), country, is_active)
- `core.users.tenant_uuid` ajouté (FK vers `core.tenants`, nullable — coexiste avec `tenant_id` String legacy)
- `core.missions` (id, cabinet_tenant_id, client_tenant_id, offre, consultant_user_id, started_at, **expires_at**, revoked_at, status, scope_tags)
- Contraintes : `tenant_type` enum, `status` enum, `cabinet_tenant_id != client_tenant_id`, `expires_at > started_at`

### Modèles ORM SQLAlchemy

`Tenant` et `Mission` dans `src/zolaos/db/models.py`. Relations `cabinet`/`client` exposées via `relationship(foreign_keys=[...])`.

### Smoke test passé

Création d'un tenant `cabinet:Polaris`, d'un tenant `client:Brazza Trading SARL` rattaché par `parent_tenant_id` → rollback OK. FKs et contraintes validées.

---

## 10. Router enrichi (modules par pôle)

### Schéma

`RouteDecision` étendu avec `module: str | None = Field(...)` (obligatoire pour forcer la grammar GBNF à le générer — sinon le champ optionnel est omis par le LLM).

### Couverture

`KNOWN_MODULES` registre par pôle (extensible) :
- `health` : `pharmacology`, `diagnosis`, `case`
- `legal` : `ohada`, `travail_cg`, `fiscal_cg`, `social_cg`, `civil_cg`, `penal_cg`, `ip_oapi`, `data_protection_cg`, `admin_cg`
- `erp` : `compta_syscohada`, `finance`, `tresorerie`, `rh`, `projets_ong`
- `grc` : `conformite`, `audit_institutionnel`, `reporting_bailleurs`, `compliance_data`, `audit_sante`
- `fintech` : `scoring`, `kyc`
- `cyber` : `defense`
- `engineering` : `code`

### Mesures

5/6 modules correctement dispatchés sur jeu de test ad-hoc. Latence routage GPU Vulkan stable ~1.3-1.7 s.

---

## 11. Récap tests passés Phase 2

| Suite | Tests | Statut |
|-------|-------|--------|
| `tests/test_eval_framework.py` | 8 | ✅ |
| `tests/test_polaris_overlay_and_reports.py` | 11 | ✅ |
| **Phase 1 (rappel)** | 30 unitaires + 3 intégration | ✅ (déjà reportés) |
| **Total Phase 2 + 1** | **52** | ✅ |

À venir (Phase 2 production) : tests `pytest -m eval` contre LLM réel sur datasets validés par experts.

---

## 12. Garantie capacités V2.2 — vérifiée

| Capacité native ZolaOS | Statut | Vérification |
|------------------------|--------|---------------|
| Génération contrats (CDI, CDD, baux OHADA, NDA) | ✅ Intact | Sous-agents Droit avec `response_schema=None` par défaut |
| Conseil pharmaco (posologie, interactions, LNME) | ✅ Intact | `PharmacologyAgent` retourne texte libre + citations |
| Gestion RH opérationnelle (modèles, calculs indemnités) | ✅ Intact | `TravailCgAgent` accessible en mode génératif |
| Optimisations fiscales (TVA, IS, IRPP) | ✅ Intact | `FiscalCgAgent` accessible en mode génératif |
| Code Agent | ⏳ Phase 3 | Non encore livré |
| Scoring crédit / KYC | ⏳ Phase 6 | Non encore livré |
| Cyber-défense | ⏳ Phase 7 | Non encore livré |
| Pôle K (langues) | ⏳ Phase 9 | Non encore livré |

Tous les sous-agents génératifs livrés Phase 2 sont accessibles **dans les deux profils** (Box et Cortex) sans contrainte d'OUTPUT_FORMAT — les overlays Polaris (`response_schema` obligatoire) sont une **couche supplémentaire** activée uniquement en profil Cortex.

---

## 13. À venir — déclencheurs non techniques

Le code Phase 2 est **prêt à recevoir des données réelles**. Ce qui reste à coordonner avec l'utilisateur :

| # | Sujet | Statut | Action utilisateur |
|---|-------|--------|---------------------|
| 13.1 | Sourcing CIM-10 | OMS (libre) | Téléchargement + ingestion via `ingest_file(..., pii_policy=NONE)` |
| 13.2 | Sourcing LNME congolaise | DPML | Contact officiel à initier |
| 13.3 | Sourcing 9 Actes Uniformes OHADA | OHADA.com (libres) | Téléchargement + ingestion `pii_policy=NONE` |
| 13.4 | Sourcing Code du Travail CG 45/75 | Journal officiel CG | À localiser (édition consolidée) |
| 13.5 | Sourcing CGI CG + dernière Loi de Finances | DGID | Contact officiel |
| 13.6 | Premier pilote cabinet d'avocats Brazzaville | Prospection | À démarrer |
| 13.7 | Premier pilote polyclinique/pharmacie | Prospection | À démarrer |
| 13.8 | Recrutement expert validateur (pharmacien) | RH | Pour valider 100 Q/R `eval` santé |
| 13.9 | Recrutement expert validateur (juriste OHADA) | RH | Pour valider 50 Q/R `eval` par module |

Une fois 13.1 + 13.3 ingérés (corpus publics), on pourra lancer une première campagne `pytest -m eval` sur les sous-agents Pharma et OHADA avec des datasets dummy enrichis → mesurer la baseline hallucination rate.

---

## 14. Phase 3 — démarrage immédiat

### Périmètre

| Task | Livrable |
|------|----------|
| **#63 Connexion sécurisée éphémère Cortex → Box** | Endpoints API box-side exposant RAG/mémoire avec auth JWT mission, middleware vérification mission, client Cortex `MissionClient`, **audit hash de chaque requête** |
| #42 (D6) Image dev avec bind-mount | Itération dev rapide |
| Pôle Engineering / Code Agent (V2.2 #25) | Premier vrai sous-agent du Pôle Engineering |

### Architecture cible Cortex → Box

```
┌────────────────────────────┐       ┌────────────────────────────┐
│  ZOLAOS_PROFILE=cortex     │       │  ZOLAOS_PROFILE=box        │
│  (chez Polaris)            │       │  (chez le client)          │
│                            │       │                            │
│  MissionClient ────────────┼──HTTP──┤ /v1/box/rag/search         │
│   - Authorization: Bearer  │  +     │  middleware verify_mission │
│     <mission JWT>          │  JWT   │  → check core.missions     │
│   - audit hash local       │        │     status='active' AND    │
│                            │        │     expires_at > now()     │
│                            │        │  → audit.log INSERT chain  │
│                            │        │  → retrieve() filtré tags  │
└────────────────────────────┘       └────────────────────────────┘
```

### Garde-fous Phase 3

- JWT mission expirable (1-3 h), `mission_id` en claim, signé HS256 avec `JWT_SECRET`
- Vérification triple : signature JWT ✓ + mission active en DB ✓ + non expirée ✓
- Toute requête Cortex → Box journalisée dans `audit.log` (chaîne hash chez le client)
- Aucune écriture distante autorisée (lecture seule via mission)
- Revocation immédiate possible : `UPDATE core.missions SET status='revoked'`

---

*Document généré automatiquement à partir de l'état du repo et de la mémoire au 2026-05-17.*
