# Journal des travaux — ZolaOS

Trace chronologique de ce qui est construit, en cours, et les décisions prises.
Le « quoi/pourquoi » synthétique ; le détail vit dans les `docs/*_ROADMAP.md` et
les messages de commit.

---

## 2026-07-30 — PSA : socle de l'outillage cabinet (feuilles de temps)

Nouvelle brique : l'**outillage métier interne du cabinet** (ce que tout cabinet de
conseil/audit/expertise utilise), distinct des modules client. On pose le **backbone
PSA** (Professional Services Automation) : feuilles de temps → économie de mission →
taux d'occupation. S'ancre sur les missions/consultants existants.

- **Modèle** `core.time_entries` (consultant × mission × jour × durée, statut
  draft→submitted→approved/rejected, **taux figés à la saisie**) + `users.grade`
  (rattachement au barème). Migration `0064`.
- **Moteur déterministe** (`zolaos/psa/`) : barème d'honoraires par grade (`rates.py`,
  config `PSA_RATE_CARD_JSON`, **prix jamais inventés** — défauts à zéro) ; économie de
  mission (`economics.py` : honoraires/coût/**marge**/WIP, `rejected` exclus) ; taux
  d'occupation (facturable/capacité). Tout en entiers (XAF sans sous-unité).
- **Endpoints** `/v1/cortex/psa/*` (profil cortex) : saisie/liste/submit des feuilles de
  temps (consultant) ; approve/reject + économie de mission + taux d'occupation + barème
  (admin). Le taux est résolu du grade du consultant et **snapshoté** à la saisie.
- **Front** : écran `/cortex/temps` (ma feuille de temps + vue cabinet économie/occupation)
  + `lib/cortex-psa.ts` + entrée Sidebar « Feuilles de temps ».
- **Doctrine** : le moteur calcule (honoraires, marge, occupation), le LLM narrera ;
  barème = décision du cabinet (config). Orienté par 2 sous-agents (tests + front).

## 2026-07-30 — Durcissement config box (synchro entitlement + RBAC)

Deux suivis résiduels de l'entitlement, réglés (`api/v1/config.py`) :

- **Synchro affichage** : `GET /v1/config` (profil box) filtre désormais `modules_actifs`
  par l'entitlement réel (`resolve_box_modules`) — l'UI n'affiche jamais un module que le
  serveur n'expose pas. Mapping code fin `pole.module` → module vendable dans
  `personalization.CODE_TO_ENTITLEMENT` (santé/droit non soumis = toujours gardés) ;
  enforcement off → aucun filtrage.
- **RBAC sur `PUT /v1/config`** : garde `require_config_editor` (rôle admin/consultant ;
  401 anonyme, 403 client). L'édition de la personnalisation n'est plus ouverte. Override
  de test par défaut dans conftest (admin), + tests dédiés du rejet client/anonyme.

## 2026-07-30 — Usage & facturation par tenant

Base de facturation cabinet. Le metering existant (`core/metering.py`) est **Redis,
éphémère (TTL 40 j), par user_id** → inadapté à la facturation. On ajoute donc du
**durable, par tenant**, sans toucher au chemin chaud du quota.

- **Grand livre durable** `core.usage_daily` (tenant_id, day, requests, tokens ;
  migration `0063`) : upsert `INSERT … ON CONFLICT` (`billing/ledger.py`). Alimenté
  **au mieux** par `require_quota` — hook **opt-in** (`BILLING_LEDGER_ENABLED`, défaut
  False), **session propre**, **fail-open** (signature de la dépendance inchangée, chemin
  metering existant intact).
- **Moteur de tarification** (`billing/pricing.py`) : **mécanisme, pas de prix inventés**.
  Barème par tier (forfait `monthly_base` + `included_requests`, dépassement par tranche
  de 1000) via `BILLING_PRICING_JSON` (défaut = zéros → coût 0). Devise défaut XAF (CEMAC).
- **Vue cortex** `GET /v1/cortex/billing?period=YYYY-MM` (cortex+admin, lecture seule) :
  agrège l'usage du mois par tenant, résout nom+tier (`core.tenants` + licence récente),
  applique le barème, trie par coût ; `GET .../pricing` = barème courant.
- **Front** : écran `/cortex/facturation` (sélecteur de mois, résumé, tableau par tenant +
  détail du coût) + `lib/cortex-billing.ts` + entrée Sidebar « Facturation ».
- **Portée** : couvre l'usage enregistré contre la base de ce déploiement ; la collecte
  inter-box (box → cortex par tunnel) est désormais implémentée (ci-dessous).

### Collecte d'usage inter-box par le tunnel

La box **remonte** son usage local au Cortex par le tunnel (comme le refresh de licence,
sens inverse), pour la facturation des déploiements hybrides.

- **Box** (`tunnel/agent.py`, `_usage_report_loop`, opt-in `USAGE_REPORT_SECONDS`, 0=off) :
  `billing/collector.collect_local_usage` agrège `core.usage_daily` local (totaux du jour +
  veille) et pousse des trames `usage_report` (fire-and-forget). Erreur DB → on saute le
  tour ; WS cassé → la reconnexion relance.
- **Cortex** (`tunnel/channel.py` + `billing/collector.ingest_reported_usage`) : `serve`
  reconnaît `usage_report` et persiste **sous l'identité AUTHENTIFIÉE de la box**
  (`self._tenant_id`, jamais le tenant du payload) via `set_usage_durable` (**écrase** les
  totaux du jour = idempotent, pas de double-comptage sur ré-rapport).
- La vue `/cortex/billing` agrège alors l'usage réel des boxes clientes.
- Tests `tests/test_usage_collection.py` (SET vs ADD, collecte, ingestion + jour invalide,
  canal, boucle désactivée).

## 2026-07-29 — Journal d'audit du cabinet

Trace horodatée des actions **sensibles** de l'exploitant cortex. **Zéro
réinvention** : au lieu d'une table parallèle, on écrit dans le journal **canonique
`audit.log`** (schéma `audit`, chaîne de hachage `payload_hash`/`prev_hash`/`row_hash`
+ triggers d'immuabilité, cf. `infra/postgres/02_audit_log.sql`) — déjà utilisé pour
les accès RAG et les missions.

- **Enregistreur** (`zolaos/audit/recorder.py`, `record_audit`) : insert dans
  `audit.log` (catégorie `security`, event=verbe, actor=principal, tenant=cible si
  tenant, payload=summary+détail) dans la **même transaction** que l'action.
- **Instrumentation** des endpoints cortex sensibles : licences (émission/révocation),
  comptes (création/màj/reset mdp — jamais le mot de passe), credential de box
  (émission/révocation), création de client. Les missions écrivaient déjà nativement.
- **Consultation** (`GET /v1/cortex/audit`, cortex+admin, lecture seule) : lit
  `audit.log`, catégories **gouvernance** par défaut (security/config/auth, écarte le
  bruit RAG), filtres event/acteur/tenant + `category=all`. `GET .../actions` = catalogue.
- **Accès lecture** : `zolaos_app` n'avait qu'INSERT sur `audit.log` ; migration `0062`
  = `GRANT SELECT` (l'immuabilité reste garantie par les triggers, pas par le refus de
  lecture — lire n'altère rien).
- **Front** : écran `/cortex/audit` (filtres + liste anté-chrono, résumé + détail
  repliable) + `lib/cortex-audit.ts` + entrée Sidebar « Journal d'audit ».

## 2026-07-29 — Cockpit de supervision (fleet)

La page « exploitation » qui manquait à cortex : vue d'ensemble des boxes clientes.
Agrège ce qui était éparpillé — connexion du **tunnel** (`REGISTRY`), **licence** +
expiration (`license_grants`), provisioning de box, **missions** actives.

- **Backend** (`api/v1/cortex_fleet.py`, `GET /v1/cortex/fleet`, cortex+admin, lecture
  seule) : par tenant client → statut licence dérivé (active/expired/revoked/none) +
  `days_left`, `box_connected` (`str(id) in REGISTRY`), `box_provisioned`, missions
  actives ; **résumé** (clients, en ligne, actives, expirant bientôt, expirées/révoquées,
  sans licence). Requêtes bornées : DISTINCT ON pour la licence la plus récente, count
  groupé pour les missions (pas de N+1). Param `expiring_days` (défaut 30).
- **Front** : écran `/cortex/supervision` (bandeau de résumé + tableau des boxes,
  badges de statut, alerte « expire bientôt ») + `lib/cortex-fleet.ts` + entrée Sidebar
  « Supervision » (admin).

## 2026-07-29 — Cockpit cortex de gestion des entitlements

Pendant **cabinet** de l'entitlement vérifié côté box : Polaris **émet, liste,
révoque et (re)livre** les licences de modules par tenant, depuis un cockpit monté
**profil cortex uniquement**, rôle **admin**. Détail : `docs/LICENSING.md`.

- **API** (`api/v1/cortex_entitlements.py`, `/v1/cortex/entitlements`) : `GET /catalogue`
  (tiers+modules pour le formulaire), `GET ""` (liste + statut dérivé), `POST ""`
  (émet = signe RS256 + persiste), `GET /{id}` (détail + jeton), `GET /tenant/{id}/active`
  (jeton vivant = socle du refresh tunnel), `POST /{id}/revoke`.
- **Persistance** (`core.license_grants`, migration `0061`) : métadonnées + jeton signé,
  **côté cortex uniquement** (la box ne voit jamais cette table). Statut **dérivé**
  (revoked > expired > active), jamais dénormalisé. **Renouvellement remplace** : émettre
  révoque les licences actives antérieures du tenant → une seule vivante.
- **Clé privée d'émission** (`ENTITLEMENT_PRIVATE_KEY`, cortex only, jamais sur une box) :
  le cockpit est le seul détenteur ; absente → `503` (pas d'émission non signée).
- **Sécurité** : profil cortex + scope `admin:users` + CSRF sur mutations ; validation
  stricte (tier/catalogue, modules ∈ MODULES, tenant type client).
- **Tests** : `tests/test_cortex_entitlements.py` — émission **vérifiable par la clé
  publique** (chaîne de confiance de bout en bout : cortex signe → box vérifie),
  renouvellement, rejets 422/503, garde admin+CSRF, révocation + livraison, 404 en box.
- **Front** (`frontend/`) : section **Licence de modules** sur la fiche client
  (`/cortex/clients/[id]`, à côté du provisioning Zolabox — la licence est par client).
  Client typé `lib/cortex-entitlements.ts` + composant `EntitlementCard` : statut/badge,
  formulaire tier (select) + modules (cases, celles du tier verrouillées) + jours,
  aperçu des modules effectifs, émission → jeton copiable, livraison du jeton vivant,
  révocation, historique. `tsc`/lint/build/vitest verts (test 404→null du client).
- **Refresh par tunnel** : la box **tire** sa licence sur son WebSocket **sortant**
  (plus de dépôt manuel). Côté cortex, `channel.serve` traite un `license_pull` →
  résout `active_license_for_tenant` (`licensing/delivery.py`) → renvoie `(statut, jeton)`.
  Côté box, `agent._refresh_loop` (initial + périodique, `ENTITLEMENT_REFRESH_SECONDS`,
  0=off) reçoit la trame `license` et `_apply_license` **écrit** le jeton (atomique) sur
  `active`, **retire** le fichier sur `revoked`/`expired` (→ fail-closed), no-op sur `none`.
  Tests `tests/test_tunnel_license.py` (14). Suite **754 passed**.
- **Application à chaud** — *révocation immédiate sans redémarrage* : au montage figé
  s'ajoute un état vivant (`licensing/state.py`, `EntitlementState` sur `app.state`) +
  une **garde runtime** (`api/entitlement_gate.py`, `require_module`) posée sur chaque
  module monté → **404** dès qu'un module quitte le jeu courant. L'agent tunnel (même
  process) appelle `refresh()` après une trame `license` → effet immédiat. Endpoint
  `GET`/`POST /v1/box/entitlement[/refresh]` (statut + forçage ops). Sens sûr :
  **réduction/révocation = immédiat** ; **extension** (module neuf) = au redémarrage.
  Tests `tests/test_entitlement_hot.py` (7). Suite **761 passed**.
- **Suivis** : synchro `GET /v1/config` sur l'entitlement ; RBAC sur `PUT /v1/config`.

## 2026-07-29 — Licence commerciale & distribution des modules (entitlement)

Correction d'un défaut **critique** (signalé « lamentable ») : `modules_actifs` était
(1) **cosmétique** (endpoints ouverts quoi qu'il arrive), (2) **éditable par le client**
(`PUT /v1/config`, aucun RBAC), (3) non persisté, (4) hors contrôle vendeur. Un client
« Compta » avait en réalité toute la box.

- **Entitlement signé Polaris** (`src/zolaos/licensing/`) : grant **RS256 asymétrique** —
  Polaris signe (clé privée), la box **vérifie** (clé publique), **ne peut pas forger**
  (prouvé en test). Modèle **HYBRIDE** : `tier` (starter/business/full) + `modules` à la
  carte. `effective_modules = tier ∪ options`, borné au catalogue.
- **Application AU MONTAGE** (`main.py`) : un module non couvert n'est **même pas monté**
  (404, absent de l'OpenAPI) — pas juste masqué. Enforcement **opt-in**
  (`ENTITLEMENT_ENFORCED`, défaut False → tout monté, dev/tests inchangés) ; **fail-closed**
  si licence absente/expirée en mode enforcé. Livraison **fichier signé et/ou refresh tunnel**.
- **Config verrouillée** (`config.py`) : `modules_actifs` **retiré** de `ConfigUpdate` — le
  client ne peut plus s'octroyer de modules ; il ne garde que la vraie personnalisation.
- **Outillage vendeur** : `scripts/gen_entitlement_keys.py` (paire RSA), `scripts/issue_license.py`
  (Polaris émet une licence signée). Runbook `docs/LICENSING.md`. Tests : infalsifiabilité,
  expiration, altération, fail-closed, montage réel (starter → seul erp monté). 17 + config réécrit.
- **Décisions actées** : packaging hybride, livraison fichier+tunnel, enforcement au montage.
- **Suivis** : refresh/révocation via tunnel cortex ; cockpit cortex pour gérer les entitlements
  par tenant ; synchro affichage `GET /v1/config` sur l'entitlement ; RBAC sur `PUT /v1/config`.

## 2026-07-28 — Champion souverain : premier sprint (couches 1 & 2)

Décision : bâtir le **champion IA souverain africain** (cf. `docs/CHAMPION_ROADMAP.md`).
Verdict d'archi : **ne pas réécrire** le moteur (déjà découplé) ; ajouter deux plans
(produit-moteur C1, données/entraînement C2) reliés par le volant de données.

Cadrage acté : portée **continentale** (français CG, lingala, kituba, swahili, wolof,
haoussa, amharique…) ; sourcing **ouvert depuis zéro** ; base **Llama-3** adaptée (LoRA).

- **L1.1 — Profil `engine` headless** — *fait* (`b88015c`). Nouveau
  `ZOLAOS_PROFILE="engine"` exposant la surface générique seule
  (`/v1/query`, `/query/stream`, `/agents` + auth + health) ; les routers verticaux/UI
  (config, feedback, kb, legal, commons) et les blocs box/cortex sont gatés hors `engine`.
  Box/cortex inchangés. `tests/test_engine_profile.py` (3 tests, isolation de surface).
- **L2.1 — Sourcing corpus langues africaines** — *fait* (`2724879`). `docs/sourcing/african_languages.md`.
  **Fait stratégique** : swahili/haoussa/amharique ont du volume ouvert commercial-clean ;
  **lingala/wolof très pauvres**, **kituba = désert total** (zéro corpus ouvert) → pour ces
  langues, **partenariats + collecte primaire** obligatoires (pas d'ouvert à ingérer).
  Pièges honnêtes : jw.org interdit le TDM ; PII sans NER bantou ; langid via GlotLID/AfroLID
  (fastText ne couvre pas lingala/kituba). Design pipeline + `training_manifest.yml` + réfs tokenizer.
- **Sprint parallèle — LIVRÉ** (6 agents simultanés, suite **681 passed**) :
  - **L1.2** (`0c4f8e0`) adaptateur **OpenAI-compatible** `/v1/chat/completions` (drop-in), tous profils.
  - **L1.3** (`0c4f8e0`) **metering + quotas/jour par clé** (Redis), `require_quota` sur query/stream/chat, **fail-open**.
  - **L1.6** (`973583a`) **harnais d'éval moteur** (routage/ancrage/abstention, 20 cas, gated LLM).
  - **L2.2** (`4d28ea1`) **tokenizer bantou** : fertility Llama-3 fr 1.67 / sw 2.60 / wo·ln 2.71 / kituba 3.00
    (+60-80 % tokens) → **garder Llama-3, différer l'extension de vocab** (corpus absent). Réf. InkubaLM/Lelapa.
  - Câblage `main.py`/`settings.py` fait à la convergence (montage OpenAI + settings quotas), zéro conflit.
  - **Correction (best practice, zéro réinvention)** : **L1.5 (volant de données/COMMONS) était DÉJÀ implémenté**
    (2026-07-07, `src/zolaos/commons/`, 13 tests verts) — la roadmap/mémoire le disaient « à coder » à tort. Corrigé.
  - **L2.4 — éval africaine** — *fait* (`fbf5e2a`) : harnais **chrF** ; FLORES-200 gated → repli **UDHR Art. 1**
    (domaine public), 15 paires FR↔{sw,ln,wo,ha,am}, 19 tests, live gated. Le mètre-étalon AVANT l'entraînement.
  - **L1.4 — packs juridiction** — *fait* (`4cf6785`) : registre `config/jurisdictions.yaml` + résolution hybride
    (X-Country/query → pays du principal → défaut) + `/v1/jurisdictions`. Injection tags retrieval = suivi L1.4b.
  - **Kit de collecte corpus** — *fait* : `docs/CORPUS_COLLECTION_KIT.md` (priorisation déserts kituba/lingala/wolof,
    types de données, canevas licence, protocole annotation, partenaires **vérifiés au web**). Outille le vrai goulot.
  - **Reste** : **couche 1 COMPLÈTE** (product-ready). Couche 2 = **data/GPU-gated** — L2.3 (SFT/LoRA), L2.5
    (registre+service), L2.6 (volant→entraînement) attendent le **corpus collecté**. **Prochaines actions = NON-code** :
    1. contacter CERELLO (`cerello@umng.cg`, seul sur kituba+lingala) ; 2. relicensing MasakhaNEWS-lingala ;
    3. GALSENAI/Baamtu pour le wolof. Cf. `docs/CORPUS_COLLECTION_KIT.md`.

## 2026-07-28 — Assistant code souverain (produit client tech, profil box)

Produit : assistant de codage exécuté **sur la box du client**, code jamais sorti.
Modèle **Qwen2.5-Coder-32B** local (dérogation actée à « stack Llama »). Détail :
`docs/CODE_ASSISTANT.md`, `project_code_assistant_souverain`.

- **P1** (`cb647de`) : schéma `rag_code` (cloisonné tenant, sensible), CodeAgent RAG-ancré,
  CodeChunker (par symboles), indexeur CLI, endpoints `/v1/code/{ask,status}`.
- **P2** (`52e28df`) : indexation **incrémentale** (hash + `--since` git + purge suppressions,
  `index_repo()`), endpoint `POST /v1/code/index` (tâche de fond).
- **P3** (`4737f25`) : **sandbox d'exécution** jetable durcie (conteneur `--network none`,
  non-root, read-only, cap-drop, limites, timeout) + `POST /v1/code/run`, **off par défaut**.
- Runbook (`c2889e0`) ; overlay Polaris code-review repointé sur `rag_code` (privé `7b93a06`).

Suite complète : **629 passed**.

## 2026-07-27 — Corpus cyber (`rag_cyber`)

Doctrine « international d'abord, congolais en bonus ». Détail : `docs/sourcing/cyber_2026.md`,
`project_rag_corpus_status`.

- Schéma + sourcing + mécanisme générique `prefer_tags` (préférence `lang:fr` sans exclure l'anglais).
- **Ingestion** (`60f73a6`) : ~5200 chunks — NIST (1019), OWASP Top10/ASVS/CheatSheets (1609),
  MITRE ATT&CK défensif (2382), 4 lois CG (193, `lang:fr`, `validated:false`+`ocr:true`).
  ANSSI laissé `pending` (conflit licence commerciale — décision juridique).

---

## Journal des décisions (durables)

- **Ne PAS réécrire le moteur** pour le champion : il est découplé, on ajoute des plans. (2026-07-28)
- **Base modèle africain = Llama-3** adaptée par LoRA ; sourcing ouvert ; portée continentale. (2026-07-28)
- **Qwen2.5-Coder-32B** pour l'assistant code (exception à « stack Llama » : qualité code = valeur). (2026-07-28)
- **Sandbox code** : option (a) socket Docker + flag off par défaut ; durcir (b)/(c) avant GA. (2026-07-28)
- **Souveraineté** : service LLM **local uniquement**, jamais d'API cloud (fallback API désactivé).
- **Doctrine** : « le moteur calcule, le LLM narre » ; abstention si non validé.
- **Corpus légal océrisé** : toujours `validated:false` + `ocr:true` (relecture humaine des chiffres avant `true`).
