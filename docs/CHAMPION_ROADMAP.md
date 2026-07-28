# Champion souverain — feuille de route couches 1 & 2

**Ambition** : faire de ZolaOS le **champion de l'IA souveraine africaine** — non pas
en imitant un labo de fondation (couche 3, moonshot continental hors de portée d'une
startup), mais en **dominant la pile souveraine + l'expertise locale + les langues
africaines** que personne d'autre ne construira. Deux couches, exécutables dès
maintenant.

## Verdict d'architecture (« faut-il tout refaire ? »)

**Non — ne pas réécrire le moteur de service.** L'orchestrateur + routeur + agents +
RAG sont **déjà découplés** du frontend (FastAPI versionné, agents-plugins, auth
par clé), cf. `docs/ARCHITECTURE_TOPOLOGIE.md` §5 et ses 6 invariants. Réécrire =
détruire un actif qui marche.

**Le vrai geste : AJOUTER deux plans** à côté du plan de service existant.

```
                 ┌─────────────────────────── VOLANT DE DONNÉES ───────────────────────────┐
                 │                                                                          │
   [Plan SERVICE existant]            [Plan PRODUIT-MOTEUR — C1]        [Plan DONNÉES & ENTRAÎNEMENT — C2]
   orchestrateur/agents/RAG    →      profil engine, contrat API,   →   corpus langues/domaines africains,
   (NE PAS réécrire)                  quotas, packs pays, commons        fine-tuning base ouverte, éval, registre
                 ↑                                                                          │
                 └──────────────── modèle adapté re-servi via le factory (déjà abstrait) ───┘
```

Seule addition réellement nouvelle : un **cycle de vie d'artefact modèle** (entraîner →
versionner → évaluer → enregistrer → servir). Il se **branche** sur l'abstraction
existante (`llm/factory.py` + `LLM_MODEL_*`) — pas une réécriture.

---

## COUCHE 1 — Champion « moteur souverain » (productisation + volant)

Objectif : le moteur devient une **API souveraine réutilisable** (référence nationale →
continentale), et **plus expert à chaque usage** (le moat façon DeepSeek : efficience +
effet de réseau de données, pas force brute).

| # | Lot | Livrable | Ampleur |
|---|---|---|---|
| **L1.1** | **Profil `engine` (headless)** | Nouveau `ZOLAOS_PROFILE="engine"` : monte UNIQUEMENT la surface générique (`/v1/query`, `/query/stream`, `/agents`, auth, health) — sans routers verticaux SaaS ni frontend. Montage conditionnel `main.py` + tests. | S |
| **L1.2** | **Contrat d'API public v1** | Figer `/v1/query` (contrat versionné, OpenAPI publié) + adaptateur **OpenAI-compatible** `/v1/chat/completions` (drop-in) + SDK minimal (py/js) + quickstart. | M |
| **L1.3** | **Metering / quotas / clés** | Quotas + rate-limit **par clé API** (Redis déjà là), metering d'usage (requêtes/tokens), export facturation, endpoints de gestion de clés. | M |
| **L1.4** | **Packs juridiction (multi-pays)** | Généraliser « pack pays » = corpus + prompts + tags par juridiction, branchables à chaud. Ajouter un pays = ajouter un pack, **pas** du code. (CG/CEMAC/OHADA = pack pilote.) | M |
| **L1.5** | **Volant de données (COMMONS)** — ✅ **DÉJÀ IMPLÉMENTÉ (2026-07-07)** | La boucle complète TOURNE (`src/zolaos/commons/`, `docs/COMMONS_PIPELINE.md` Phases A/B/C) : feedback → anonymisation → quarantaine → k-anonymat(3) → validation humaine → promotion `rag_commons`. **Le moat qui compose est en place.** Reste à le brancher sur l'entraînement (L2.6). | ✅ |
| **L1.6** | **Harnais d'éval moteur** | Suite auto (justesse de routage, qualité d'ancrage/citation, abstention correcte, latence) qui tourne au fil du passage à l'échelle → pas de régression. Étend `tests/eval/`. | M |

**Définition de « fait » couche 1** : un tiers (autre projet/pays africain) peut obtenir
une clé, appeler `/v1/query`, être facturé à l'usage, brancher son propre pack pays — et
le moteur s'améliore mesurablement à chaque déploiement.

---

## COUCHE 2 — Adaptation modèle africain (plan données & entraînement, greenfield)

Objectif : **notre modèle** — pas un pré-entraînement frontière (100 M$+), mais
l'**adaptation d'une base ouverte** sur langues + données africaines. 100-1000× moins
cher, et c'est là que naît l'identité « modèle africain ». **Plan séparé du service.**

| # | Lot | Livrable | Ampleur |
|---|---|---|---|
| **L2.1** | **Pipeline corpus langues/domaines africains** | L'actif le plus durable. Collecte (démarrer : **français CG, lingala, kituba/munukutuba** ; puis swahili…), discipline de licence (réutiliser la rigueur `docs/sourcing/` + manifeste), nettoyage/dédup/PII/scoring qualité. Manifeste **d'entraînement** (distinct du RAG). | L |
| **L2.2** | **Base + tokenizer** | Choisir une base ouverte (Llama-3 / Qwen2.5 / GLM). **Point dur** : les tokenizers fragmentent mal les langues bantoues (coût + qualité) → analyser, éventuellement **étendre le vocabulaire**. Doc de décision + analyse tokenizer sur texte africain. | M |
| **L2.3** | **Adaptation (SFT/LoRA d'abord)** | Instruction-tuning de la base sur données africaines. **Démarrer LoRA/QLoRA** (peu coûteux, 1 GPU) → prouver l'uplift → passer au fine-tune complet / continued-pretraining si le volume le justifie. Pipeline reproductible (HF/axolotl/unsloth), configs versionnées. | L |
| **L2.4** | **Éval africaine (à construire — rien n'existe)** | Bancs langues + domaines locaux (traduction, compréhension, QA droit/santé CG). Sans mesure, pas de preuve « meilleur localement ». Partagé avec L1.6. | M |
| **L2.5** | **Registre modèle + service** | Versionner/enregistrer le modèle adapté ; le câbler dans `factory.make_*_client` + `LLM_MODEL_*` → il devient un modèle **sélectionnable** du moteur (patron déjà prouvé avec Qwen pour le code). | S |
| **L2.6** | **Fermer le volant** | Relier L1.5 (commons/feedback validé) → L2.1 (données d'entraînement) → prochain fine-tune → re-servi. **Le moteur composé qui apprend de son propre usage.** | M |

**Définition de « fait » couche 2** : un modèle adapté, servi localement (souverain),
**mesurablement meilleur** que la base sur les langues/domaines africains, et
ré-entraînable depuis les données validées par l'usage.

---

## Transverse (contraintes honnêtes)

- **Compute** : L2.3-4 exigent du GPU. LoRA = 1×A100/H100 louable (accessible) ;
  fine-tune complet / CPT = cluster (gate capital + **énergie**, le vrai goulot africain).
  **Stratégie : commencer LoRA (peu cher), scaler au financement.**
- **Souveraineté** : service **local uniquement** (poids ouverts) — jamais d'API cloud
  pour le raisonnement (respecte « fallback API désactivé »). GLM/Kimi K2 ont des poids
  ouverts → servables en local si on veut une base plus costaude que Llama-3.
- **Doctrine préservée** : « le moteur calcule, le LLM narre » — l'adaptation modèle ne
  touche pas les moteurs déterministes (droit/fiscal/…). Abstention si non validé.
- **Licence** : cœur **AGPL v3** (partageable = référence nationale) ; l'offre engine
  porte sur le cœur, pas les overlays Polaris.

## Séquencement recommandé

1. **Démarrer en parallèle, tout de suite** :
   - **L1.1** (profil engine) — petit, débloque le récit « moteur réutilisable ».
   - **L2.1** (collecte corpus langues africaines) — **long-pole + moat durable**, à lancer immédiatement car c'est ce qui prend le plus de temps et que personne d'autre ne fera.
2. **Puis** L1.2/L1.3 (contrat + facturation → ça finance) et L2.2/L2.3 (base + LoRA → premier « modèle africain » démontrable).
3. **Ensuite** L2.6 (fermer le volant vers l'entraînement — **L1.5 commons est déjà en place**) — la mécanique qui compose et rend le moat inrattrapable.
4. L1.4, L1.6, L2.4, L2.5 en soutien continu.

> Le premier pas *concret* vers « notre DeepSeek » n'est ni un GPU géant ni une levée :
> c'est **L1.1 (profil engine)** + **L2.1 (corpus langues africaines)**. Le reste
> s'enchaîne, se finance et se prouve au fur et à mesure.
