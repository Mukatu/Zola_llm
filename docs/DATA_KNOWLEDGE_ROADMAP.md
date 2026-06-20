# Roadmap Données & Connaissance — comment « nourrir » ZolaOS

**Date** : 2026-06-20
**Objet** : procédure et sources pour alimenter les sous-agents (tous pôles) **avant** déploiement, puis boucle d'amélioration **après** déploiement. Réponse structurée à : « comment nourrir le LLM avant qu'il puisse s'améliorer une fois opérationnel ? »
**Références** : `ZOLAOS_MASTER_PLAN_V2.md` §2.3 (persistance), §9.3 (fine-tuning LoRA), vision §3 (apprentissage fédéré) ; `ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md` §2.4 ; pipeline `src/zolaos/rag/` + `src/zolaos/eval/`.

---

## 0. Clarification fondamentale — un LLM ne « s'auto-entraîne » pas

Trois couches distinctes, souvent confondues :

| Couche | Ce que c'est | Mécanisme | Entraîne le modèle ? |
|--------|--------------|-----------|----------------------|
| **1. RAG (connaissance)** | Corpus texte récupéré au moment de la requête | ingestion → embeddings bge-m3 → pgvector → retrieval | ❌ Non (récupération) |
| **2. Référence structurée** | Plans de comptes, barèmes, listes (LNME, CIM-10) | tables/ressources, logique métier | ❌ Non |
| **3. Auto-amélioration** | Le système devient meilleur avec l'usage | feedback → eval → enrichissement corpus / prompts → *fine-tuning* / *fédéré* | ✅ Oui, mais **humain dans la boucle**, périodique, jamais automatique seul |

> « Nourrir » au quotidien = couches 1 & 2 (immédiat, pipeline déjà construit). « S'améliorer » = couche 3 (à concevoir, Phase 4-5+).

---

## 1. Couche 1 & 2 — Amorçage (bootstrap) avant déploiement

### Pipeline déjà en place
- `rag/ingest.py` : `ingest_file()` / `ingest_text()` idempotents, **hook PII bloquant** (politique explicite obligatoire sur schéma sensible).
- `rag/chunking_specialized.py` : chunkers `LegalArticleChunker`, `AccountingChunker`, `MedicalCaseChunker`…
- `rag/embeddings.py` : bge-m3 (1024d).
- `eval/` : framework de mesure (hallucination, citation precision/recall) → baseline.

### Procédure type (par corpus)
1. **Sourcer** le corpus (cf. §3) + vérifier **licence**.
2. Choisir la **politique PII** (`NONE` pour corpus public, `FISCAL`/`RH`/`MEDICAL` sinon).
3. `ingest_file(path, schema="rag_<pole>", tags=["country:cg","module:<m>"], pii_policy=...)`.
4. Vérifier l'indexation (compte de chunks, `pii_stats` en `extra_metadata`).
5. Lancer `pytest -m eval` sur un dataset vérité-terrain → **baseline hallucination**.
6. Itérer : ajuster chunker/seuils, ré-ingérer si besoin.

### Référence structurée (couche 2)
Chargée comme **ressource** (JSON/CSV → table ou fichier de référence), pas via le RAG : plan de comptes SYSCOHADA, barèmes fiscaux, LNME. Utilisée par la logique métier (validation d'écritures, lookup) et par les connecteurs ERP.

---

## 2. Besoins de données par sous-agent

Légende statut : 🟢 dispo/identifié · 🟠 partiel · 🔴 à sourcer · ⚫ différé.

| Pôle / agent | Donnée | Type | Schéma cible | Source candidate | Licence | Statut | PII |
|--------------|--------|------|--------------|------------------|---------|--------|-----|
| Droit / `ohada` | 9 Actes Uniformes (articles) | RAG | `rag_legal` | HF `Maathis-com/ohada-actes-uniformes` | CC-BY-4.0 | 🟢 | NONE |
| Droit / `fiscal_cg` | CGI CG + Loi de Finances | RAG | `rag_legal` | DGID (officiel) | publique | 🔴 | NONE |
| Droit / `travail_cg` | Code du travail 45/75 + conv. coll. | RAG | `rag_legal` | Journal Officiel CG | publique | 🔴 | NONE |
| Droit / `admin_cg` | Code marchés publics, ARMP | RAG | `rag_legal` | officiel CG | publique | 🔴 | NONE |
| Santé / `pharmacology` | CIM-10 | RAG | `rag_health` | OMS (libre) | OMS | 🔴 | NONE |
| Santé / `pharmacology` | LNME congolaise | structuré+RAG | `rag_health` | DPML | publique | 🔴 | NONE |
| ERP / `compta` (à créer) | **Texte AUDCIF (droit comptable)** | RAG | `rag_erp` | HF OHADA dataset (AUDCIF) | CC-BY-4.0 | 🟢 | NONE |
| ERP / `compta` (à créer) | **Plan de comptes SYSCOHADA révisé** | **structuré** | ressource JSON | template ERPNext / norme publique | voir §3 | 🟠 | NONE |
| ERP / `fiscal` (à créer) | Barèmes TVA/IS/IRPP CG | structuré | ressource | CGI / DGID | publique | 🔴 | NONE |
| ERP / `rh` (à créer) | Réutilise `travail_cg` + barèmes CNSS | RAG+struct | `rag_legal` | cf. ci-dessus | — | 🟠 | RH |
| ERP / `finance` (à créer) | Flux bancaires/MoMo (données client) | live | connecteurs | Connector Framework | — | 🟢 (méca) | FISCAL |
| GRC / `reporting_bailleurs` | Standards IATI/PRAG/OECD-DAC | RAG | `rag_grc` (futur) | sites bailleurs | variable | ⚫ | NONE |
| Fintech / `scoring`,`kyc` | Signaux MoMo + listes sanctions | live+struct | connecteurs | Phase 6 | — | ⚫ | FISCAL |

> Les agents ERP peuvent être **codés maintenant** avec `rag_schema` placeholder (pattern existant) ; corpus ingéré ensuite, **sans modif de code**.

---

## 3. Sources identifiées et vérifiées (2026-06-20)

### 🟢 RAG juridique OHADA — `Maathis-com/ohada-actes-uniformes` (HuggingFace)
- **Licence** : CC-BY-4.0 → ingestion + redistribution OK **avec attribution** (à ajouter dans `NOTICE`).
- **Format** : CSV (nodes/edges) + Parquet (corpus GraphRAG), **français**.
- **Couverture** : 3 126 articles, **les 9 Actes Uniformes** (AUSCGIE, AUSCOOP, AUPC, AUDCG, AUPSRVE, AUS, **AUDCIF** = droit comptable, AUA, AUCTMR) + 15 380 liens vers jurisprudence CCJA.
- **Atout** : découpage article-par-article = aligné avec `LegalArticleChunker` et le retrieval ; couvre directement les agents `ohada` et le **texte comptable** (AUDCIF) de l'agent Compta.
- **Limite** : ne contient **pas** le plan de comptes détaillé (annexe SYSCOHADA) → couche 2 ci-dessous.

### 🟠 Plan de comptes SYSCOHADA (structuré)
- **Candidats** : template ERPNext `syscohada_syscohada_chart_template.json` (projet ERPNext, GPLv3) ; module Odoo `cameroun/l10n_cm_syscohada`.
- **Nuance droit d'auteur** : le plan de comptes SYSCOHADA révisé (2017) est une **norme réglementaire publique** (numéros + libellés = faits) → faible risque ; la *compilation* JSON peut porter la licence du projet source.
- **Recommandation** : reconstruire notre propre JSON canonique à partir du plan officiel (sûr), en s'inspirant du template ERPNext comme référence de structure. À faire valider par le pôle Droit/Polaris.
- `ericzile/Syscohada` **écarté** (application Android, pas une source de données).

### 🔴 À sourcer (côté utilisateur, contacts officiels)
CIM-10 (OMS, libre), LNME (DPML), Code du travail CG 45/75 + conventions collectives (Journal Officiel CG), CGI CG + dernière Loi de Finances (DGID), Code des marchés publics (ARMP).

---

## 4. Couche 3 — Auto-amélioration après déploiement (procédure)

Mise en place **progressive**, jamais automatique sans contrôle :

1. **Capture du feedback** (post-MVP) : pouce ✓/✗ + correction utilisateur sur chaque réponse ; stockage avec `request_id` + contexte récupéré (s'appuie sur `audit.log`).
2. **Évaluation continue** : alimenter les datasets `eval/` avec les cas réels validés par experts → suivi du taux d'hallucination dans le temps.
3. **Amélioration sans réentraînement (priorité)** :
   - enrichissement du corpus RAG (combler les manques détectés),
   - ajustement des prompts versionnés (`agents/prompts/`),
   - réglage des seuils `min_confidence`.
4. **Fine-tuning léger** (si plateau mesuré, cf. §9.3 plan) : adaptateurs **LoRA** sur Llama-3-8B, par domaine, à partir des jeux validés. Reste **Llama** (cf. licence + mémoire projet).
5. **Apprentissage fédéré** (vision §3, addendum « Phase 4-5 ») : agrégation de gradients **chiffrés** inter-Box sans exfiltrer les données client. **À concevoir** (PoC dédié) — dépend de l'architecture Zero Trust.

> Ordre : 3 (corpus/prompts) en continu dès le MVP → 4 (LoRA) si nécessaire → 5 (fédéré) en R&D. Toujours validation humaine sur santé/droit/fiscal avant production (directive §5.7).

---

## 5. Gouvernance des données

- **PII** : politique explicite par corpus à l'ingestion (hook bloquant). Public = `NONE` ; données client = `FISCAL`/`RH`/`MEDICAL`.
- **Licences** : tracer chaque source (licence + attribution) dans `NOTICE` / `THIRD_PARTY_LICENSES.md`. CC-BY → attribution obligatoire.
- **Versionnement corpus** : `source_uri` + `pii_stats` + politique en `extra_metadata` → ré-ingestion/audit possible.
- **Validation experts** : pharmacien (santé), juriste OHADA (droit) — prérequis avant production sur ces domaines.
- **Multi-pays** : tag `country:<iso>` systématique ; l'extension = nouvelle donnée, pas réécriture.

---

## 6. Statut & prochaines actions

| Action | Quand | Responsable |
|--------|-------|-------------|
| Coder les sous-agents ERP (RH/Finance/Compta) avec corpus différé | **prochain chantier** | assistant |
| Construire le JSON canonique plan de comptes SYSCOHADA (couche 2) | avec l'agent Compta | assistant (+ validation Droit) |
| Ingérer le corpus OHADA HF (CC-BY-4.0) + attribution NOTICE | dès `rag_erp`/`rag_legal` prêts | assistant |
| Sourcer corpus 🔴 (CIM-10, CGI, Code travail, LNME) | en parallèle | utilisateur |
| Baseline `eval` (hallucination) après 1ère ingestion réelle | après ingestion | assistant |
| Concevoir la boucle feedback + apprentissage fédéré (PoC) | Phase 4-5 | à planifier |

---

*Roadmap données/connaissance établie le 2026-06-20. Couvre tous les pôles ; sources vérifiées par recherche web le même jour.*
