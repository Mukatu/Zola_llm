# Architecture & topologie — moteur, Zolabox, Zolacortex

**Date** : 2026-07-02
**Objet** : clarifier ce qu'est le *moteur* d'IA souveraine, sa frontière avec la *connaissance*, et sa relation avec les déploiements **Zolabox** (client) et **Zolacortex** (cabinet). Fixe aussi deux exigences directrices : **le moteur doit rester autonome** (utilisable comme API générique multi-projets, à terme référence nationale) et **perpétuellement plus expert** sur les sujets locaux.
**Voir aussi** : `docs/DATA_KNOWLEDGE_ROADMAP.md` (comment nourrir/faire progresser la connaissance), `docs/PRODUCT_STRATEGY.md` (moteur = moat), `docs/PERSISTENCE_ROADMAP.md` (store métier).

---

## 1. Les trois choses à ne pas confondre

| Terme | Ce que c'est | Nature |
|-------|--------------|--------|
| **ZolaOS** | Le **moteur** : IA souveraine = orchestrateur + routeur + agents métier + clients LLM | **Un composant logiciel** (le cœur) |
| **La Zolabox** | Déploiement de ZolaOS **chez le client** : moteur + modules + données du client (actifs publics V2.2) | **Une topologie de déploiement** |
| **Zolacortex** | Déploiement de ZolaOS **chez le cabinet** (Polaris) : le **même moteur** + prompts confidentiels de mission + inférence LLM des missions d'audit | **Une topologie de déploiement** |

> **Convention de nommage.** *ZolaOS* désigne le **moteur** (l'IA souveraine / orchestrateur), en complément des deux déploiements *Zolabox* (client) et *Zolacortex* (cabinet). Le moteur ZolaOS est un **sous-ensemble** de la Zolabox et de Zolacortex, pas un produit distinct : « Zolabox » et « Zolacortex » = **deux façons de déployer le même moteur ZolaOS**, avec des périmètres de données et de confidentialité différents.

---

## 2. ZolaOS (le moteur) — anatomie (fichiers réels)

Pipeline : **Router → (Planning) → Agent(s) → réponse fusionnée**.

| Brique | Fichier | Rôle |
|--------|---------|------|
| Orchestrateur | `src/zolaos/core/orchestrator.py` | Compose le pipeline, mesure la latence |
| Routeur | `src/zolaos/agents/router.py` | Classe la requête dans un pôle (Llama-3-8B, JSON strict) |
| Méta-agent Planning | `src/zolaos/agents/meta/planning.py` | Décompose les requêtes complexes |
| Brigade / agents métier | `src/zolaos/agents/**` | Un sous-agent par module métier (voir §2.1) |
| Clients LLM | `src/zolaos/llm/factory.py` | Routeur 8B (port 11434) + cœur 70B (port 11435) ; backends `llamacpp` (OpenAI-compatible) ou `ollama` |
| RAG | `src/zolaos/rag/` + `src/zolaos/agents/rag_agent.py` | Récupération + ancrage + citations |
| Mémoire sémantique | `src/zolaos/agents/meta/memory.py` | `remember()` / `recall()`, filtrage RBAC par tags |
| Persistance métier | `src/zolaos/db/store_*` | Système de référence léger par tenant (`store_*`) |

### 2.1 Pôles connus (routeur)
`health · legal · erp · grc · fintech · cyber · engineering · general` — chacun avec ses modules (`agents/router.py::KNOWN_MODULES`). Un module inconnu est **accepté et loggué** (extensible sans casser le routage). Un agent métier se contente de déclarer `name`, `rag_schema`, `prompt_file`, `default_tags` — **la connaissance est injectée par données, pas codée en dur** (cf. `RAGAgent`).

---

## 3. La frontière essentielle — moteur (raisonnement) vs connaissance (données)

C'est le point le plus souvent mal compris. **Le LLM ne « connaît » pas le Congo. Il raisonne ; la connaissance locale vit dans les données.**

| Couche | Contenu | Où | Réentraîne le modèle ? |
|--------|---------|-----|------------------------|
| **Modèle** | Llama-3 (8B routeur, 70B cœur), souverain, local | poids figés | ❌ Jamais en production automatique |
| **RAG (connaissance textuelle)** | Lois, conventions, jurisprudence, CIM-10… | `rag_legal`, `rag_health` (pgvector) | ❌ Récupération à la requête |
| **Référence structurée** | Barèmes, plans de comptes, SMIG, cotisations | JSON/tables `ref` (ex. `agents/erp/ref/payroll_cg.json`) | ❌ Lookup déterministe |
| **Persistance métier** | Données du client (bulletins, écritures, factures…) | `store_*` par tenant | ❌ |
| **Mémoire sémantique** | Faits appris, cas validés | `MemoryEntry` (pgvector, tags RBAC) | ❌ (récupération) |

**Conséquence pratique** : tout le savoir-faire Congo (barème de paie, DAS 1, droit OHADA, LNME…) est **corrigeable sans réentraîner quoi que ce soit** — on édite une donnée, un corpus, un prompt. Illustration vécue : le sourcing fiscal/paie (PAIE-4) a atterri dans `ref/payroll_cg.json` (paramètres du calcul **déterministe**) et `docs/REFERENTIEL_DROIT_TRAVAIL_CG.md` (corpus documentaire), **jamais dans les poids** de Llama-3.

**Règle d'or (déjà appliquée)** : le chiffre est **déterministe** (barème structuré), le LLM ne sert qu'à **expliquer / justifier / citer**. Un bulletin de paie, une écriture comptable, ne sont jamais « inventés » par le modèle. Garde-fous anti-hallucination dans `rag_agent.py` : `requires_citation` (refus si 0 extrait) et `min_confidence` (refus si similarité trop faible).

---

## 4. Zolabox vs Zolacortex — la même machine, deux périmètres

Modèle **Zero Trust Client** (cf. mémoire projet + addendum Polaris) :

```
   ┌────────────────────────┐        liaison sécurisée        ┌────────────────────────┐
   │   ZOLACORTEX (cabinet) │◄──────── éphémère (JWT) ────────►│    ZOLABOX (client)    │
   │                        │        temps d'une mission       │                        │
   │  • même MOTEUR         │                                  │  • même MOTEUR         │
   │  • prompts de mission  │   Cortex interroge le RAG du      │  • actifs PUBLICS V2.2 │
   │    (confidentiels)     │   client SANS rapatrier ses       │  • données du client   │
   │  • inférence des       │   données (MissionClient →        │    (restent chez lui)  │
   │    missions d'audit     │   rag_search distant, RBAC tags) │                        │
   └────────────────────────┘                                  └────────────────────────┘
```

- **Zolacortex n'est pas qu'une interface** : c'est là que tourne l'orchestration **sensible** des missions (prompts + inférence propriétaires du cabinet). C'est le *moat*.
- **Zolabox ne contient que du public** : le savoir-faire du cabinet n'y descend jamais.
- Le retrieve distant passe par `MissionClient` (`agents/rag_agent.py::_do_retrieve` → branche `mission_client`), avec token de mission et filtrage par tags. Profils `cortex` vs `box` (cf. `core/profiles.py`).
- **Même codebase des deux côtés** : la différence est de **configuration et de données**, pas de code.

---

## 5. Exigence n°1 — le moteur doit rester AUTONOME (API générique)

Objectif : que le moteur d'orchestration + ses agents métier puisse, au besoin ou à l'avenir, être **exposé comme une API générique multi-projets** — comme les IA du marché (DeepSeek, Claude, Mistral) — pour doter le pays d'une **référence souveraine**.

### 5.1 État actuel — déjà largement découplé
- Le moteur est exposé via **FastAPI versionné** (`src/zolaos/api/v1/`), indépendant du frontend.
- Le backend LLM local est **OpenAI-compatible** (`LlamaCppClient`) : n'importe quel projet tiers peut, en principe, consommer le modèle comme une API standard.
- L'orchestrateur ne dépend d'aucun module métier en dur : les agents s'ajoutent par pôle, la connaissance s'injecte par **données taggées** (`country:*`, `module:*`, `tenant:*`).
- Le **fallback externe est désactivé par défaut** (`ENABLE_EXTERNAL_FALLBACK`, guard dans `llm/factory.py`) → souveraineté verrouillée par conception.

### 5.2 Invariants à préserver (pour ne pas « re-coupler » le moteur)
1. **Aucune dépendance dure moteur → module** : un agent métier reste un *plugin* (déclare `name/rag_schema/prompt_file/default_tags`), jamais une condition en dur dans l'orchestrateur.
2. **Connaissance = donnée, jamais code** : un taux, une loi, un barème → RAG ou `ref`/`store`, jamais une constante enfouie dans la logique.
3. **Multi-tenant / multi-pays par tag** : `country:<iso>` + `tenant:<id>` systématiques ; l'extension à un nouveau pays = **nouvelle donnée**, pas réécriture.
4. **Contrat d'API stable et versionné** (`/v1/…`) : ce qui serait exposé « en générique » doit avoir un contrat public documenté, découplé des écrans.
5. **Frontière de licence nette** : cœur moteur **AGPL v3** (partageable, référence nationale) vs overlays Polaris **propriétaires** (Zero Trust). Une exposition API générique porte sur le **cœur**, pas sur les missions cabinet.
6. **Garde-fous transverses** : anti-hallucination (`requires_citation`, `min_confidence`), PII bloquant à l'ingestion, RBAC par tags — valables quel que soit le consommateur de l'API.

> Tant que ces 6 invariants tiennent, « exposer le moteur comme API générique » reste une **décision produit** (facturation, licence, quotas), pas un chantier de ré-architecture.

---

## 6. Exigence n°2 — rendre le moteur PERPÉTUELLEMENT plus expert (surtout local)

La procédure détaillée vit dans `docs/DATA_KNOWLEDGE_ROADMAP.md`. Rappel de l'ossature + l'angle « expertise locale par métier ».

### 6.1 Trois leviers, un seul avec réentraînement
1. **Enrichir le RAG** (immédiat, pipeline en place) : ingérer lois/conventions/jurisprudence/cas → `ingest_file(schema="rag_<pole>", tags=[...], pii_policy=...)`. Idempotent, PII bloquant.
2. **Enrichir la référence structurée** (immédiat) : barèmes, plans de comptes, grilles conventionnelles → JSON/`ref`, **gouvernés** (voir §6.3).
3. **Auto-amélioration** (progressive, humain dans la boucle) : feedback ✓/✗ + correction → datasets `eval/` → enrichissement corpus/prompts/seuils → *LoRA* Llama-3 si plateau mesuré → apprentissage **fédéré** inter-Box (R&D). **Jamais automatique sans validation** sur santé/droit/fiscal.

### 6.2 Là où se fabrique l'expertise locale — chaque module est un gisement
Point clé pour la stratégie : **chaque module qu'on construit produit deux matières premières d'expertise** —
- **(a) une référence structurée locale** (ex. Paie : barème CG, prime d'ancienneté par paliers, DAS 1) — déjà versionnée et gouvernée ;
- **(b) des cas réels validés en production** (bulletins, écritures, dossiers) — la « jurisprudence opérationnelle » qui, une fois validée par un expert, alimente l'auto-amélioration.

> L'expertise locale ne s'achète pas d'un coup : elle **s'accumule à l'usage** des modules. Plus la Zolabox tourne chez des clients congolais, plus le moteur dispose de cas validés — à condition d'avoir la **boucle de feedback** (couche 3) branchée.

### 6.3 Gouvernance — la condition de confiance (déjà en place sur la Paie)
- **Drapeau `validated`** sur les données réglementaires : émission refusée tant qu'un expert n'a pas validé ; **toute édition incrémente la version ⇒ re-validation obligatoire** (modèle Paie, à généraliser).
- **Sourcé ≠ confirmé** : le barème CG est sourcé mais reste `validated:false` tant qu'il n'est pas croisé au texte primaire.
- **Tagging discipliné** : `type:texte_legal` vs `type:jurisprudence` / `type:doctrine` ; le texte de loi prime, la jurisprudence illustre.
- **Validation experte** (pharmacien / juriste OHADA) prérequis avant production sur santé/droit/fiscal.
- **Licences tracées** (`NOTICE` / `THIRD_PARTY_LICENSES.md`) pour tout corpus ingéré.

---

## 7. Synthèse en une phrase

**ZolaOS** — le **moteur** (orchestrateur + agents + Llama-3 souverain) — est un composant **autonome et découplé**, déployé tel quel dans la **Zolabox** (client, données publiques) et dans **Zolacortex** (cabinet, missions confidentielles) ; toute l'intelligence *locale* vit dans les **données** (RAG + référence structurée + store + mémoire), jamais dans les poids du modèle ; il peut donc devenir une **API générique de référence nationale** sans ré-architecture — et il se rend **perpétuellement plus expert** en accumulant, module après module, des références structurées gouvernées et des cas réels validés.

---

*Document établi le 2026-07-02. Décrit la topologie au niveau architectural ; les contenus confidentiels de mission (prompts cabinet) ne sont pas documentés ici.*
