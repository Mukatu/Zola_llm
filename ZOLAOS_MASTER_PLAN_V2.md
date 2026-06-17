# PLAN D'ACTION ZOLAOS — VERSION 2.2
# Plateforme IA multi-agents souveraine — Marché initial : République du Congo (Brazzaville)
# Révision du 2026-05-14
# Changements V2.2 : focalisation RC, Pôle Droit en 8 modules, ajout Pôle GRC, Connector Framework générique, stack technique enrichi

---

## 1. RÔLE ET VISION

**ZolaOS** est un écosystème multi-agents hiérarchique (HMAS) **souverain**, conçu pour s'exécuter **exclusivement en local** (Asus ROG, 128 Go RAM, via Ollama). La capacité de fallback API externe (Anthropic) est **codée mais désactivée par défaut** — activation manuelle uniquement si les tests démontrent que le modèle local plafonne sur des sujets critiques (voir §2.7).

### 1.1. Marché initial : République du Congo (Brazzaville)
**ZolaOS sera intégralement construit et mûri pour la République du Congo** (Congo-Brazzaville, capitale Brazzaville, zone CEMAC, monnaie XAF). À ne pas confondre avec la RDC (Kinshasa, zone CEEAC, monnaie CDF).

Toute extension sous-régionale ou internationale est **différée** à une phase post-stabilisation. L'architecture est dès le départ pensée multi-pays (tagging `country:cg`, schémas RAG par pays/module) afin que l'extension future soit une question de **données**, pas de **réécriture**.

### 1.2. Cadres réglementaires applicables
- **OHADA** : droit des affaires (Congo = État partie fondateur), SYSCOHADA pour la comptabilité
- **CEMAC + BEAC** : monnaie XAF, supervision bancaire par la **COBAC**
- **OAPI** (Accord de Bangui) : propriété intellectuelle
- **CIPRES** : prévoyance sociale harmonisée
- **Législation nationale congolaise** : Code du travail 45/75, CGI, Loi 29-2019 (données personnelles), Code de la santé publique, etc.
- **Régulateurs** : DGID (impôts), CNSS (sécurité sociale), DPML (pharmacie), ARPCE (télécoms/données), ANIF (anti-blanchiment)

### 1.3. Pôles métiers (par priorité)
- **Santé** (pharmacologie, CIM-10 + LNME congolais, posologie)
- **Droit** (8 modules : OHADA + droit national congolais)
- **Code Agent / Engineering** — accélérateur transversal (dogfooding interne)
- **ERP** (RH, Finance, SYSCOHADA, déclarations DGID/CNSS) — **pilier critique du modèle économique**
- **GRC** (Gouvernance, Risque, Conformité — pôle transversal)
- **Fintech** (scoring crédit, KYC, intégration MTN MoMo + Airtel Money Congo)
- **Cyber-défense** (défensif strict)
- **Pôle K** (Lingala + Kituba/Munukutuba — langues du Congo) — **traité en phase finale**

---

## 2. ARCHITECTURE DE RÉFÉRENCE

### 2.1. Topologie
- **Router léger (amont)** : Llama-3-8B classifieur **100 % local** → décide du pôle métier et de l'agent cible. Évite d'invoquer le 70B sur des requêtes triviales.
- **ZolaOS Core (Orchestrateur lourd)** : Llama-3-70B local. Fusion des réponses, arbitrage, sécurité.
- **Brigade de sous-agents experts** : **Llama-3-8B** uniformément, spécialisés par system prompt strict + RAG dédié. **Famille Llama imposée** (8B agents + 70B Core) pour cohérence de tokenizer, de prompt format et de comportement, et pour simplifier les mises à jour de modèle.
- **Méta-agents transversaux** : Mémoire, Planification, Auto-correction, **Supervision/Sécurité**. (Méta-agent Traduction = phase finale, voir Pôle K.)

### 2.2. Stack technique
| Couche                 | Choix                                                                | Plan B (si volumétrie/charge l'exige)        |
|------------------------|----------------------------------------------------------------------|-----------------------------------------------|
| Inference LLM          | **Ollama** (llama.cpp, gguf)                                         | vLLM (Phase 8)                                |
| API                    | **FastAPI** + **Pydantic v2**                                        | —                                             |
| DB relationnel + vecteurs | **PostgreSQL + pgvector**                                        | Hybride : PG + **Qdrant** si > 5 M vecteurs/index |
| Cache + sessions       | **Redis**                                                            | —                                             |
| Queue / tâches async   | **Dramatiq** (Redis-backed)                                          | RQ                                            |
| Stockage objet         | **MinIO** (S3-compatible, self-hosted)                               | —                                             |
| Reverse proxy + TLS    | **Caddy**                                                            | Traefik                                       |
| Migrations DB          | **Alembic**                                                          | —                                             |
| Logs structurés        | **structlog** → **Loki**                                             | —                                             |
| Métriques              | **Prometheus + Grafana**                                             | —                                             |
| Traces                 | **OpenTelemetry**                                                    | —                                             |
| Secrets (prod)         | `.env` chiffré → **Vault** ou **Doppler self-hosted** (Phase 4+)     | —                                             |
| Embeddings             | **bge-m3** (MIT, multilingue, 8K context, dense+sparse+multivector) | —                                             |
| Sandbox d'exécution    | **Docker éphémère** durci (Phase 3+)                                 | **gVisor** (`runsc`) en Phase 8 si code tiers |

### 2.3. Persistance et données
- **PostgreSQL + pgvector**, séparé en schémas isolés :
  - `core` (sessions, utilisateurs, RBAC, API keys)
  - `memory` (mémoire sémantique partagée, tags d'accès)
  - `rag_health` (santé + LNME congolais)
  - `rag_legal_ohada`, `rag_legal_labor_cg`, `rag_legal_tax_cg`, `rag_legal_social_cg`, `rag_legal_civil_cg`, `rag_legal_criminal_cg`, `rag_legal_ip_oapi`, `rag_legal_data_cg` (un schéma par module juridique)
  - `rag_erp` (référentiels ERP, templates SYSCOHADA)
  - `rag_code` (codebase indexé par le Code Agent)
  - `rag_locales` (corpus langues locales : Lingala, Kituba)
  - `audit` (journal append-only, voir `infra/postgres/02_audit_log.sql`)
- **Tagging multi-pays généralisé** : chaque chunk porte un tag `country:<iso>` (`country:cg` par défaut). Extension future = nouveau pays sans refonte schéma.
- **Chiffrement at-rest** dès le départ. Backups automatisés (pg_dump quotidien + WAL streaming).

### 2.4. Connector Framework générique (B2B / ERP / systèmes maison)
Couche d'abstraction unique pour brancher ZolaOS à n'importe quel système externe (ERP, comptabilité, banque, paie, maison).

```
zolaos/connectors/
├── base.py              # Interface abstraite ERPConnector / FinanceConnector / etc.
├── odoo.py              # XML-RPC / JSON-RPC
├── erpnext.py           # REST
├── sage.py              # API ou ODBC
├── generic_rest.py      # REST configurable (OpenAPI)
├── generic_soap.py      # SOAP / WSDL
├── generic_sql.py       # DB direct via SQLAlchemy
├── csv_excel.py         # Ingestion fichiers + watcher dossier
├── webhook.py           # Entrée par webhooks
└── custom_sdk/          # SDK + docs clients (systèmes maison)
```

Principes :
- **Interface unique** : `list_employees()`, `read_invoice()`, `push_journal_entry()`, etc.
- **Mapping déclaratif** YAML : `employee.full_name → person.nom_complet` sans code.
- **Auth pluggable** : API key, OAuth2, basic, certificats, IP allowlist.
- **SDK Custom** : un client implémente `CustomConnector(BaseConnector)` (5-6 méthodes), ZolaOS le découvre via config.

### 2.5. Pôle Engineering — Code Agent
Sous-agent spécialisé pour les **grands projets de programmation**, distinct par sa surface d'outils et son besoin de mémoire longue.
- **Modèle** : Llama-3-70B pour le raisonnement architectural ; Llama-3-8B pour les tâches mécaniques.
- **Outils sandboxés** : `safe_read`, `safe_write`, `safe_exec`, `safe_git`, `run_tests`.
- **Sandbox** : Docker éphémère (`--rm --network none --read-only --user non-root`, limites cgroup).
- **Mémoire projet** : schéma `rag_code` + watcher fichiers + cache AST (tree-sitter).
- **Garde-fous** : allowlist chemins, blocklist commandes destructives, audit complet, mode revue diff > 100 lignes.

### 2.6. Pôle GRC — Gouvernance, Risque, Conformité (transversal)
**Pôle transversal** qui consomme les données et corpus des autres pôles.
- **Audit légal** : vérifie conformité OHADA + droit national CG.
- **Gestion des risques** : opérationnels, juridiques, financiers, cyber — scoring + plan d'atténuation.
- **Reporting réglementaire** : génération automatique (CNPS/CNSS, DGID, ARPCE, ANIF, BEAC/COBAC).
- **Veille réglementaire** : surveille évolutions textes, alerte sur impacts.
- **Contrôle interne** : séparation des tâches, traçabilité, anomalies (s'appuie sur `audit.log`).

### 2.7. Politique de fallback API (désactivé par défaut)
- Le module `external_llm` (connecteur Anthropic) **est implémenté** dès la Phase 0 mais piloté par un **feature flag global** `ENABLE_EXTERNAL_FALLBACK=false`.
- Tant que le flag est `false` : **aucun appel sortant possible**. Garde-fou en amont du client HTTP + test d'intégration CI à chaque commit.
- **Activation manuelle uniquement** après rapport documenté de plafonnement local sur un sujet critique.
- Si activé un jour : **PII redaction** + plafond budgétaire + circuit breaker deviennent prérequis obligatoires.

### 2.8. Infrastructure et exposition
- API FastAPI versionnée (`/v1/`), authentification clé API + JWT.
- Reverse proxy **Caddy** avec TLS automatique.
- **Docker Compose** dès la Phase 0 (Postgres + Redis + MinIO + Ollama + app + Caddy).
- Conçu pour un **serveur local** unique avec onduleur — coupures électriques et connectivité dégradée intégrées comme hypothèses de base.

---

## 3. FEUILLE DE ROUTE PROGRESSIVE

### PHASE 0 — Socle technique transverse [Semaines 1-2]

Objectif : poser les fondations qualité/sécurité/observabilité **avant** tout code métier.

- **0.1** Arborescence : `/agents`, `/connectors`, `/core`, `/rag`, `/tools`, `/tests`, `/infra`, `/docs`, `main.py`, `.env.example`.
- **0.2** Gestion des secrets : `.env` chiffré + variables d'environnement, jamais en clair dans le repo. `gitleaks` en CI.
- **0.3** CI/CD : GitHub Actions (lint `ruff`, format `black`, tests `pytest`, scan `gitleaks`).
- **0.4** Observabilité : `structlog` JSON, **Prometheus + Grafana**, traces **OpenTelemetry**, logs vers **Loki**.
- **0.5** Environnements : `dev` (local), `staging` (Docker), `prod` (Docker + serveur physique). `.env.{env}`.
- **0.6** Versioning des prompts : dossier `/agents/prompts/` versionné, chaque prompt = fichier `.md` + métadonnées + tests de régression.
- **0.7** Anti-injection by design : sanitization entrées utilisateur, séparation stricte system/user, allowlist outils par agent.
- **0.8** Docker Compose initial : Postgres + Redis + MinIO + Caddy + Ollama + app.
- **0.9** Migrations DB : Alembic configuré, init scripts `infra/postgres/01_init_schemas.sql` + `02_audit_log.sql` joués automatiquement.

**Critères de sortie** :
- CI verte, couverture tests > 60 % du socle
- Dashboard Grafana de base
- README + CONTRIBUTING publiés
- `docker compose up` fonctionne end-to-end

---

### PHASE 1 — Fondations système [Mois 1] **PRIORITÉ INDICE 1**

#### Volet A — Squelette orchestrateur
- **1.A.1** Connecteurs Python : `OllamaClient` + `ExternalLLMClient` (désactivé par flag). Interface unifiée `LLMClient`.
- **1.A.2** Router léger 100 % local : classifieur Llama-3-8B (Santé / Droit / ERP / GRC / Fintech / Général) retournant un JSON de routage.
- **1.A.3** Squelette FastAPI : `/v1/query`, `/v1/health`, `/v1/agents`. Middleware auth + rate limiting.
- **1.A.4** Méta-agent Mémoire : interface pgvector (insert, search top-k avec tags `country:cg` + tags d'accès, TTL).
- **1.A.5** Méta-agent Planification : décomposition ReAct / Plan-and-Execute.

#### Volet B — Sécurité de base
- **1.B.1** RBAC par tags pgvector : `public`, `health`, `legal:<module>`, `erp`, `tenant:X`, `country:cg`.
- **1.B.2** Sandboxing des outils : wrapper qui logue + valide chaque appel.
- **1.B.3** "Safe Write" générique : aucun agent ne peut écrire un fichier sans validateur centralisé.
- **1.B.4** Garde-fou anti-fallback : test d'intégration CI vérifie 0 requête sortante tant que `ENABLE_EXTERNAL_FALLBACK=false`.

**Critères de sortie** :
- Une requête Router → Orchestrateur → Agent simulé retourne en < 2 s.
- Tests d'intégration sur les 3 méta-agents.
- Garde-fou fallback validé en CI.

**KPI** : latence p95 < 2 s, taux d'erreur < 1 %, couverture tests > 70 %.

---

### PHASE 2 — MVP commercial Santé & Droit [Mois 2-3]

#### 2.1 Sous-agent Pharmacologie (Pôle Santé)
- Sourcing **CIM-10** (OMS, libre) + **LNME congolaise** (Liste Nationale des Médicaments Essentiels, DPML) + posologies pédiatriques/adultes.
- Pipeline RAG : ingestion → chunking (512 tokens, overlap 64) → embeddings `bge-m3` → indexation `rag_health` (tag `country:cg`).
- Fonction de **vérification de stock** (mock initial, intégration ERP en Phase 4 via Connector Framework).
- Cas d'usage prioritaires Brazzaville : antipaludéens, antirétroviraux, antibiotiques courants, génériques disponibles localement.
- **Évaluation RAG** : 100 questions vérité-terrain validées par un pharmacien congolais. Cible : hallucination < 5 % in-domain.

#### 2.2 Sous-agent Droit (8 modules, focalisation CG)
Démarrage **3 modules prioritaires** pour le MVP, les 5 autres déployés progressivement en Phase 2-bis (intégrée à Phase 4).

**MVP Phase 2** :
- **Droit des affaires OHADA** : 9 actes uniformes (libres de droits). Templates contrats : société (SARL/SAS-OHADA), cession de parts, sûretés.
- **Droit du travail CG** : Code du travail 45/75 consolidé, conventions collectives (commerce, hydrocarbures, BTP), modèles : CDI, CDD, lettre de licenciement, rupture conventionnelle.
- **Droit fiscal CG** : CGI congolais, dernière Loi de Finances, déclarations TVA / IS / IRPP / retenues à la source.

**Modules différés (Phase 4 +)** :
- Droit social CG (CNSS, CIPRES)
- Droit civil CG (famille, succession, baux civils)
- Droit pénal des affaires (Code pénal CG + OHADA pénal)
- Propriété intellectuelle (OAPI)
- Données personnelles (Loi 29-2019)

**Pour chaque module** : RAG dédié (`rag_legal_<module>_cg`), génération avec **citation obligatoire** (article + texte), garde-fou anti-hallucination renforcé (refus de réponse si confiance < seuil).

**Évaluation** : 50 cas de génération par module validés par un juriste pilote (cf. 2.4).

#### 2.3 Sécurisation et conformité
- Chiffrement at-rest activé (TDE PostgreSQL ou volumes chiffrés).
- **Audit trail** complet (santé, droit, ERP) : utilisateur, timestamp, hash sortie.
- **PII redaction** : module présent mais inactif tant que le fallback API est désactivé.
- Plan de conformité documenté : **Loi 29-2019 CG** + obligations sectorielles santé (DPML) et droit (déontologie avocats).

#### 2.4 Pilote terrain Brazzaville / Pointe-Noire
- **Cabinet d'avocats** 2-5 associés à Brazzaville, spécialisé OHADA + droit du travail.
- **Pharmacie d'officine ou polyclinique** 10-50 lits, Brazzaville ou Pointe-Noire.
- Convention pilote 3 mois gratuit contre feedback structuré + droit d'usage anonymisé.
- Recueil structuré : NPS, taux d'usage, bugs critiques, cas non couverts.

**KPI sortie Phase 2** :
- Hallucination rate < 5 % (in-domain)
- Latence p95 < 3 s
- 2 pilotes actifs avec ≥ 50 requêtes/semaine
- 3 modules juridiques en production

---

### PHASE 3 — Pôle Engineering / Code Agent [Mois 4] **ACCÉLÉRATEUR TRANSVERSAL**

Livré juste avant la Phase 4 ERP pour dogfooding immédiat sur les connecteurs.

#### 3.1 Infrastructure code
- Schéma `rag_code` : indexation incrémentale (fichiers, symboles, docstrings), embeddings `bge-m3`.
- Watcher de modifications (inotify / fswatch), ré-embarquage incrémental.
- Cache AST (tree-sitter) pour Python, TypeScript, SQL, Dockerfile, YAML.

#### 3.2 Outils sandboxés (Docker éphémère)
- `safe_read` / `safe_write` : allowlist workspaces.
- `safe_exec` : Docker éphémère (`--rm --network none --read-only`, timeout, user non-root, limites cgroup).
- `safe_git` : lecture git par défaut ; commit/branch sous flag explicite.
- `run_tests` : pytest / vitest / go test dans sandbox.

#### 3.3 Orchestration multi-étapes (Plan-and-Execute)
- Llama-3-70B découpe la tâche → délégation Llama-3-8B en parallèle quand indépendant.
- Boucle de validation : chaque sous-tâche produit un diff, agrégation par le 70B, présentation utilisateur avant application.
- Mode revue obligatoire si changeset > 100 lignes ou fichiers sensibles (`.env`, configs DB, CI/CD).

#### 3.4 Garde-fous
- Allowlist stricte (`/workspace/<project>/**`).
- Blocklist commandes destructives (`rm -rf`, `git push --force`, `DROP`, `TRUNCATE`, `chmod -R 777`).
- Tout `tool_call` loguée dans `audit.log` (entrée/sortie hashées).
- Réseau désactivé dans le sandbox par défaut.

#### 3.5 Évaluation
- Benchmark 20 tâches de référence (refactor, génération tests, debug, ajout feature).
- **Critère de sortie** : ≥ 70 % de réussite sans correction lourde.

**KPI sortie Phase 3** :
- Code Agent dogfoodé en interne pour Phase 4
- 0 incident de sécurité
- Couverture tests Code Agent > 80 %

---

### PHASE 4 — Pôle ERP [Mois 5-6] **PILIER CRITIQUE**

Socle de revenus récurrents et point d'entrée naturel chez les PME congolaises.

#### 4.1 Sous-agent RH
- Tri de CV (extraction structurée, scoring, anti-biais).
- Conformité contrats de travail **Code du travail CG + OHADA** (corpus Phase 2).
- Génération : fiches de poste, lettres d'embauche, contrats CDI/CDD, notifications disciplinaires.

#### 4.2 Sous-agent Finance
- Analyse flux de trésorerie (relevés bancaires XAF, MoMo, Airtel Money, factures).
- Détection d'anomalies (doublons, dépassements, échéances).
- Génération rapports synthétiques (mensuel, trimestriel) au format DGID-compatible.

#### 4.3 Sous-agent Comptabilité & Fiscalité CG
- **SYSCOHADA révisé** : plan comptable, écritures, états financiers.
- Pré-saisie d'écritures, contrôle de cohérence.
- **Déclarations fiscales CG** : TVA mensuelle, IS, IRPP, retenues — formats DGID.
- **Déclarations sociales CG** : DTE/DGE, cotisations CNSS.

#### 4.4 Connector Framework + intégrations
- Livraison du **Connector Framework** (cf. §2.4).
- Connecteurs livrés en standard : **Odoo**, **ERPNext**, **REST générique**, **CSV/Excel**.
- SDK Custom + documentation pour systèmes maison.

#### 4.5 Pilote B2B Brazzaville / Pointe-Noire
- **2 PME pilotes** (20-100 salariés), secteur services ou négoce.
- Accompagnement intégration, mesure d'impact (temps gagné, qualité, NPS).

#### 4.6 Modules juridiques complémentaires
- Activation des 5 modules juridiques différés depuis Phase 2 (social, civil, pénal des affaires, OAPI, données personnelles).

**KPI sortie Phase 4** :
- 2 PME en production
- Réduction ≥ 30 % du temps de traitement RH/comptable
- Hallucination rate < 3 % sur sorties comptables/fiscales
- Connector Framework documenté, ≥ 1 connecteur maison déployé chez pilote
- Mode 100 % local confirmé (0 appel sortant)

---

### PHASE 5 — Pôle GRC (Gouvernance, Risque, Conformité) [Mois 7] **TRANSVERSAL**

Pôle transversal s'appuyant sur Droit (corpus) + ERP (données métier) + Audit (journal).

#### 5.1 Sous-agent Audit légal
- Vérification conformité **OHADA + droit national CG** sur contrats, statuts, procédures.
- Détection de clauses non conformes ou risquées.

#### 5.2 Sous-agent Gestion des risques
- Cartographie : opérationnels, juridiques, financiers, cyber.
- Scoring et plan d'atténuation.

#### 5.3 Sous-agent Reporting réglementaire
- **CNSS** : déclarations mensuelles/annuelles.
- **DGID** : déclarations fiscales.
- **ANIF** : déclarations de soupçon (LAB-FT).
- **ARPCE** : formalités données personnelles.
- **COBAC/BEAC** : reporting bancaire (pour Phase 6 Fintech).

#### 5.4 Sous-agent Veille réglementaire
- Surveillance évolutions Lois de Finances annuelles, modifications OHADA, nouvelles obligations sectorielles.
- Alerte impact sur clients existants.

#### 5.5 Contrôle interne
- Séparation des tâches, traçabilité (s'appuie sur `audit.log` et son intégrité par hashing).
- Détection d'anomalies sur opérations critiques.

**KPI sortie Phase 5** :
- 100 % des déclarations réglementaires CG couvertes par templates
- Veille en production avec alertes hebdomadaires
- 1 client GRC dédié signé

---

### PHASE 6 — Fintech (Scoring crédit & KYC) [Mois 8]

- **6.1** Sous-agent **Scoring crédit** pour microfinance : agrégation signaux (historique MoMo Congo, Airtel Money, comportement transactionnel, déclaratif).
- **6.2** Sous-agent **KYC/AML** : vérification d'identité, screening listes de sanctions, détection de patterns suspects. Conformité **ANIF** + **COBAC**.
- **6.3** Connecteurs : **MTN Mobile Money Congo** + **Airtel Money Congo** (sandboxs d'abord, prod sur autorisation). Pas de M-Pesa (marché est-africain).
- **6.4** Conformité bancaire : reporting **BEAC/COBAC**, intégration avec pôle GRC.

**KPI** : 1 client microfinance signé, scoring validé sur jeu de test ≥ AUC 0,75.

---

### PHASE 7 — Cyber-défense **défensive** [Mois 9+]

Recadrage : **uniquement défensif, jamais offensif, jamais autonome sur actions actives**.

- **7.1** Sous-agent **audit de configuration** : SSH, nginx, postgres → recommandations.
- **7.2** Sous-agent **détection d'anomalies** : analyse logs (auth, accès) avec alerting.
- **7.3** Sous-agent **conformité durcissement** : CIS Benchmarks adaptés au contexte CG.
- **Interdictions explicites** : aucune action offensive, aucune exploitation, aucune modification distante. Toute action active = validation humaine obligatoire.

**KPI** : couverture de 10 contrôles CIS, 0 faux positif critique.

---

### PHASE 8 — Industrialisation et scalabilité [Mois 10+]

- **8.1** Renforcement anti-injection (méta-agent Supervision) : pattern detection avancé, red teaming périodique.
- **8.2** Optimisation conteneurs : images Docker minimales, multi-stage build, healthchecks.
- **8.3** Migration **Gitea self-hosted** pour souveraineté repo (depuis GitHub privé initial).
- **8.4** Migration éventuelle Ollama → **vLLM** si throughput insuffisant.
- **8.5** Migration sandbox Code Agent → **gVisor** si exécution de code tiers (marketplace, plugins clients).
- **8.6** Préparation extension sous-régionale CEMAC : kit de déploiement pour serveurs physiques locaux (Pointe-Noire, puis Libreville, Douala…). Activation des tags `country:ga`, `country:cm`, etc.
- **8.7** Documentation opérationnelle : runbooks, plan DRP (Disaster Recovery), procédures rotation secrets.

---

### PHASE 9 — Pôle K (langues du Congo) [Mois 12+] **PHASE FINALE**

Traitée **en dernier**, plateforme stabilisée et marché CG validé.

#### 9.1 Langues prioritaires (recentrées sur le marché CG)
- **Lingala** (Brazzaville et Nord-Congo)
- **Kituba / Munukutuba** (Pointe-Noire et Sud-Congo)
- *(Swahili et Wolof retirés du périmètre initial : non pertinents en RC. Réservés à l'extension sous-régionale future.)*

#### 9.2 Industrialisation du méta-agent Traduction
- Sur la base d'un POC léger exécuté en parallèle de la Phase 1 (hors chemin critique).
- Intégration FR ↔ Lingala / Kituba, extensible.
- Hooks STT/TTS prêts (intégration vocale différée).

#### 9.3 Pipeline d'évaluation continue
- Corpus d'évaluation enrichi (≥ 1000 phrases par langue, validé par locuteurs natifs congolais).
- Métriques BLEU / chrF / évaluation humaine.
- Amélioration : fine-tuning léger ou adaptateurs LoRA si bge-m3 + Llama-3-8B insuffisants.

#### 9.4 Activation cross-pôles
- Tous les sous-agents (Santé, Droit, ERP, GRC) acceptent entrée en lingala/kituba et répondent en lingala/kituba.
- Cache des traductions fréquentes.

**KPI sortie Phase 9** :
- BLEU ≥ 30 sur lingala et kituba
- Évaluation humaine ≥ 4/5 sur 100 phrases tirées au sort
- Latence supplémentaire < 500 ms vs requête FR

---

## 4. KPI TRANSVERSES

| Catégorie       | Métrique                            | Cible MVP (Phase 2)    |
|-----------------|-------------------------------------|------------------------|
| Performance     | Latence p95                         | < 3 s                  |
| Performance     | Throughput                          | 10 req/s soutenu       |
| Qualité         | Taux d'hallucination (in-domain)    | < 5 % (santé/droit), < 3 % (compta/fiscal Phase 4) |
| Qualité         | Recall@5 RAG                        | > 80 %                 |
| Fiabilité       | Disponibilité mode local            | 99 % offline           |
| Coût            | Coût mensuel d'infra locale         | budget à fixer         |
| Sécurité        | Couverture tests anti-injection     | > 90 %                 |
| Sécurité        | Appels sortants (flag off)          | **0** (vérifié CI)     |
| Conformité      | Couverture déclarations CG (Phase 5)| 100 %                  |
| Adoption        | Pilotes actifs (CG)                 | ≥ 2 fin Phase 2, ≥ 4 fin Phase 4 |

---

## 5. DIRECTIVES DE TRAVAIL

1. **Raisonnement explicite** : avant tout code structurant, analyser l'impact architectural.
2. **Modularité stricte** : orchestrateur, connecteurs, outils, sous-agents totalement découplés. Interfaces explicites.
3. **Sécurité by design** : aucune commande destructrice ; chaque connexion DB validée ; secrets jamais en clair.
4. **Orientation terrain CG** : coupures électriques, connectivité dégradée, langues locales = hypothèses de base, pas exceptions.
5. **Mesure systématique** : chaque feature livrée vient avec métriques + tests de régression.
6. **Versioning des prompts** : code critique, traités comme tels.
7. **Validation humaine** sur domaines à risque (santé, droit, sécurité, fiscal) avant production.
8. **Souveraineté repo** : pas de GitHub-specific dans le code ; tout doit être migrable vers Gitea (Phase 8).
9. **Multi-pays par tagging** : jamais de constante `"CG"` en dur ; toujours `country:<iso>` paramétrable.

---

## 6. ASSIGNATION DES MODÈLES (RAPPEL CLAUDE CODE)

| Modèle | ID                          | Usage                                                                |
|--------|-----------------------------|----------------------------------------------------------------------|
| Haiku  | `claude-haiku-4-5-20251001` | Tâches mécaniques : tests, lint, docs, grep, refactoring simple      |
| Sonnet | `claude-sonnet-4-6`         | Implémentation standard : features, debug, revue de code             |
| Opus   | `claude-opus-4-7`           | Décisions architecturales : design système, sécurité, refactoring majeur |

**Règle de décomposition** : toute tâche multi-étapes est décomposée en sous-agents lancés en parallèle quand indépendants. Le modèle le plus léger capable du travail est toujours préféré.

---

## 7. DÉCISIONS TRANCHÉES

| Décision                       | Choix                                            | Migration future       |
|--------------------------------|--------------------------------------------------|------------------------|
| Repo                           | **GitHub privé** (vélocité Actions)              | → Gitea self-hosted Phase 8 |
| Embedding                      | **bge-m3** (MIT, multilingue, 8K context)        | —                      |
| Sandbox Code Agent             | **Docker éphémère durci**                        | → gVisor Phase 8 si code tiers |
| LLM serving                    | **Ollama**                                       | → vLLM Phase 8 si besoin |
| Vector store                   | **PostgreSQL + pgvector**                        | → Qdrant si > 5 M vecteurs/index |
| Fallback API                   | **Désactivé par défaut** (`ENABLE_EXTERNAL_FALLBACK=false`) | Activation manuelle uniquement |

---

## 8. PROCHAINES ÉTAPES (avant Phase 0)

À amorcer en parallèle (cycles longs) :

1. **Recrutement pilotes Brazzaville / Pointe-Noire** :
   - 1 cabinet d'avocats (OHADA + droit du travail)
   - 1 pharmacie ou polyclinique
   - 1-2 PME pour Phase 4 ERP (cycle de vente B2B 3-6 mois)
2. **Sourcing corpus juridique CG** — point bloquant connu :
   - Code du travail 45/75 consolidé à jour
   - Conventions collectives sectorielles
   - CGI congolais + dernière Loi de Finances
   - Loi 29-2019 sur les données personnelles
   - Texte de référence : un contact juriste/avocat indispensable pour la version consolidée
3. **Sourcing corpus santé CG** :
   - LNME congolaise (DPML)
   - Liste des génériques disponibles localement
4. **Validation budget infra locale** : serveur, onduleur, backup, connectivité de secours.

Une fois les pilotes identifiés et les corpus juridiques sourcés (au moins partiellement), exécution de la **Phase 0** en autonomie.
