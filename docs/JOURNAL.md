# Journal des travaux — ZolaOS

Trace chronologique de ce qui est construit, en cours, et les décisions prises.
Le « quoi/pourquoi » synthétique ; le détail vit dans les `docs/*_ROADMAP.md` et
les messages de commit.

---

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
- **Suivis** : job de refresh par tunnel (tirer `/tenant/{id}/active` côté box) ;
  synchro `GET /v1/config` ; RBAC sur `PUT /v1/config`.

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
