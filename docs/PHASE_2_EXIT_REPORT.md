# ZolaOS — Rapport de sortie Phase 2 (revue de clôture)

**Date** : 2026-06-20
**Objet** : évaluation des critères de sortie de la Phase 2 (MVP Santé + Droit + RAG) et verdict de clôture.
**Verdict** : 🟢 **GO technique** / 🟠 **NO-GO commercial conditionnel** — le périmètre code est complet et vérifié ; la *déclaration de sortie* effective reste suspendue à 4 prérequis terrain non techniques (corpus réels, ≥ 1 pilote, baseline `eval`, validation experts).

**Références** :
- [`PHASE_1_REPORT.md`](./PHASE_1_REPORT.md) · [`PHASE_2_REPORT.md`](./PHASE_2_REPORT.md) · [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md) · [`PHASE_4_REPORT.md`](./PHASE_4_REPORT.md)
- KPI de référence : [`ZOLAOS_MASTER_PLAN_V2.md`](../ZOLAOS_MASTER_PLAN_V2.md) + ajustements [`ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md) §7

---

## 1. Critères de sortie — tableau de bord

| # | Critère de sortie Phase 2 | Cible | État | Verdict |
|---|---------------------------|-------|------|---------|
| C1 | 3 modules juridiques livrés | OHADA, Travail CG, Fiscal CG | Sous-agents livrés + prompts versionnés + garde-fou anti-hallucination | 🟢 code OK |
| C2 | Sous-agent Santé (Pharmacologie) | livré | `PharmacologyAgent` + chunker médical + PII MEDICAL | 🟢 code OK |
| C3 | Pipeline RAG bge-m3 | ingestion + chunking + retrieval RBAC | 7 loaders, 4 chunkers spécialisés, HNSW + GIN, anti-leak tags | 🟢 code OK |
| C4 | PII redaction (prérequis bloquant) | hook obligatoire pré-ingestion | 5 politiques, hook `ValueError` sur schéma sensible sans politique | 🟢 code OK |
| C5 | Conformité OUTPUT_FORMAT overlays | 100 % des appels overlays | `PolarisOverlay` impose `response_schema` (sinon refus à l'init) | 🟢 code OK |
| C6 | Rapport `.docx` généré + validé | ≥ 1 sur mission test | `build_report` testé bout-en-bout (Fiscal + RH) | 🟢 code OK |
| C7 | Latence routage p95 | < 3 s | mesuré médiane 1,34 s / max 1,39 s (Strix Halo Vulkan) | 🟢 atteint |
| C8 | Latence e2e | ≤ 8 s (enveloppe Strix Halo sans GPU dédié) | 3,5 s (ERP) → 13,5 s (contrat OHADA long) | 🟠 partiel |
| C9 | Hallucination rate in-domain | < 5 % | **non mesurable** sans corpus réels + datasets validés | 🔴 bloqué |
| C10 | 2 pilotes actifs ≥ 50 req/sem | 1 = Polaris + 1 client réel | aucun pilote démarré | 🔴 bloqué |

**Synthèse** : 6 critères techniques verts (C1–C6), 1 atteint (C7), 1 partiel hardware (C8), 2 bloqués par des dépendances terrain (C9, C10).

---

## 2. Preuve de l'état technique (vérifié le 2026-06-20)

- **Tests** : 117 collectés → **114 passés, 0 échec**, 3 désélectionnés (`integration`/`eval`, nécessitent Postgres/Redis/LLM réel). Run sur image `zolaos:dev-test` (Python 3.12).
- **Génération `.docx`** : validée bout-en-bout après réintégration des dépendances documentaires (`python-docx`, `openpyxl`, `pypdf`) dans l'image — cf. [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md) §7.
- **Modèle** : Llama-3 sur toute la stack (8B routeur/brigade, 70B planning). Aucune dérive (le `Modelfile` qwen est un artefact non câblé).
- **Versionnement** : cœur open-core AGPL v3 (`github.com/Mukatu/Zola_llm`) + actifs Polaris privés séparés (frontière `strip_polaris_assets.sh`).

---

## 3. Ce qui bloque la déclaration de sortie (non technique)

| Prérequis | Détail | Responsable | Débloque |
|-----------|--------|-------------|----------|
| **P1 — Corpus publics** | CIM-10 (OMS) + 9 Actes Uniformes OHADA → ingestion `pii_policy=NONE` | Utilisateur (téléchargement direct) | C9 (partiel) |
| **P2 — Corpus nationaux** | Code du travail CG 45/75, CGI CG + dernière Loi de Finances, LNME (DPML) | Utilisateur (contacts officiels) | C9, C1, C2 (qualité) |
| **P3 — Baseline `eval`** | `pytest -m eval` sur datasets vérité-terrain une fois P1 ingéré → mesurer hallucination rate | Assistant (dès corpus dispo) | C9 |
| **P4 — Pilotes terrain** | 1er = Polaris (consultants sur cas test Cortex) + 1 client réel (cabinet/polyclinique/PME Brazzaville) | Utilisateur (prospection) | C10 |
| **P5 — Validation experts** | Pharmacien (100 Q/R santé) + juriste OHADA (50 cas/module) pour valider les datasets `eval` | Utilisateur (recrutement) | C9 (fiabilité) |

> Ordre conseillé : **P1** (corpus publics, immédiat) → **P3** (baseline hallucination) → **P2/P5** (corpus nationaux + validation) → **P4** (pilotes). P1+P3 peuvent démarrer sans dépendance externe forte.

---

## 4. Risques résiduels / dette portée en Phase 4+

| ID | Sujet | Sévérité | Suivi |
|----|-------|----------|-------|
| C8 | e2e > 3 s sur réponses longues (sans GPU dédié) | Moyenne | cible p95 < 2 s exige GPU prod ; enveloppe Strix Halo acceptée en MVP |
| P4.1 | Schémas RAG dédiés `rag_erp`/`rag_grc` (placeholders sur `rag_legal`) | Moyenne | Phase 4 — cf. [`PHASE_4_REPORT.md`](./PHASE_4_REPORT.md) §4 |
| D1 | Routage variable selon requête (cold path GBNF) | Faible | à instrumenter |

---

## 5. Décision

**La Phase 2 est close côté ingénierie** : tous les livrables de code, garde-fous et tests sont en place et vérifiés (C1–C7). La **sortie commerciale** (déclaration « Phase 2 released ») est **conditionnée** à l'exécution de P1→P5, qui relèvent du terrain et non du code.

**Action immédiate recommandée** : démarrer **P1 + P3** — ingérer les corpus publics (CIM-10, OHADA) et lancer la première campagne `eval` pour obtenir une baseline mesurée du taux d'hallucination. C'est le plus court chemin pour faire passer C9 de 🔴 à une valeur chiffrée, et la dernière vraie inconnue technique avant la sortie.

---

*Document généré à partir de l'état du repo, des tests et de la mémoire au 2026-06-20.*
