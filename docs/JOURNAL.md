# Journal des travaux — ZolaOS

Trace chronologique de ce qui est construit, en cours, et les décisions prises.
Le « quoi/pourquoi » synthétique ; le détail vit dans les `docs/*_ROADMAP.md` et
les messages de commit.

---

## 2026-07-28 — Champion souverain : premier sprint (couches 1 & 2)

Décision : bâtir le **champion IA souverain africain** (cf. `docs/CHAMPION_ROADMAP.md`).
Verdict d'archi : **ne pas réécrire** le moteur (déjà découplé) ; ajouter deux plans
(produit-moteur C1, données/entraînement C2) reliés par le volant de données.

Cadrage acté : portée **continentale** (français CG, lingala, kituba, swahili, wolof,
haoussa, amharique…) ; sourcing **ouvert depuis zéro** ; base **Llama-3** adaptée (LoRA).

- **L1.1 — Profil `engine` headless** — *fait, à committer*. Nouveau
  `ZOLAOS_PROFILE="engine"` exposant la surface générique seule
  (`/v1/query`, `/query/stream`, `/agents` + auth + health) ; les routers verticaux/UI
  (config, feedback, kb, legal, commons) et les blocs box/cortex sont gatés hors `engine`.
  Box/cortex inchangés. `tests/test_engine_profile.py` (3 tests, isolation de surface).
- **L2.1 — Sourcing corpus langues africaines** — *fait, à committer*. `docs/sourcing/african_languages.md`.
  **Fait stratégique** : swahili/haoussa/amharique ont du volume ouvert commercial-clean ;
  **lingala/wolof très pauvres**, **kituba = désert total** (zéro corpus ouvert) → pour ces
  langues, **partenariats + collecte primaire** obligatoires (pas d'ouvert à ingérer).
  Pièges honnêtes : jw.org interdit le TDM ; PII sans NER bantou ; langid via GlotLID/AfroLID
  (fastText ne couvre pas lingala/kituba). Design pipeline + `training_manifest.yml` + réfs tokenizer.
- **Sprint parallèle en cours** : L1.2 (adaptateur OpenAI-compatible), L1.3 (metering/quotas par clé),
  L1.6 (harnais d'éval moteur), L2.2 (analyse tokenizer bantou). Fichiers disjoints ; câblage à la convergence.

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
