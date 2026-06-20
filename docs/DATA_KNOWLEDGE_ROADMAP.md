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
| Droit (transversal) | **Jurisprudence CCJA** (arrêts) | RAG **précédent** | `rag_legal` + tag `type:jurisprudence` | HF OHADA-CCJA corpus (~4 059) / ohada.com / juricaf | à vérifier | 🟠 | NONE |
| Droit national CG | Jurisprudence Cour Suprême CG (social/civil/commercial) | RAG précédent | `rag_legal` + `type:jurisprudence` | juricaf / ohada.com (déc. nationales) | à vérifier | 🔴 | NONE |
| Fiscal | Doctrine administrative / rescrits DGID | RAG pratique | `rag_legal` + `type:doctrine` | DGID | publique | 🔴 | NONE |
| Santé / `pharmacology` | CIM-10 | RAG | `rag_health` | OMS (libre) | OMS | 🔴 | NONE |
| Santé / `pharmacology` | LNME congolaise | structuré+RAG | `rag_health` | DPML | publique | 🔴 | NONE |
| ERP / `compta` | Texte AUDCIF (droit comptable) | RAG | `rag_erp` | HF OHADA (AUDCIF) | CC-BY-4.0 | 🟢 | NONE |
| ERP / `compta` | **Plan de comptes SYSCOHADA révisé** | **structuré (table réf.)** | `ref` | norme publique / template ERPNext | voir §3 | 🟠 | NONE |
| ERP / `fiscal` | CGI CG + Loi de Finances 47-2024 | RAG | `rag_legal` | finances.gouv.cg (officiel) | publique | 🟠 | NONE |
| ERP / `fiscal` | Barèmes TVA/IS/IRPP/retenues | structuré | `ref` | CGI (extraits) | publique | 🟠 | NONE |
| ERP / `rh` | Code travail 1975-45 + décrets | RAG | `rag_legal` | JO `sgg.cg` | publique | 🟠 | NONE |
| ERP / `rh` | Conventions collectives sectorielles (pétrole/BTP/commerce) | RAG | `rag_legal` | branches / JO étendu | variable | 🔴 | NONE |
| ERP / `rh` | SMIG/SMAG + barèmes de paie | structuré | `ref` | décrets (SMIG 70 400 FCFA, 2025) | publique | 🟠 | NONE |
| ERP / `rh` | Cotisations CNSS + prévoyance CIPRES | structuré | `ref` | CNSS / CIPRES | publique | 🔴 | RH |
| ERP / `rh` | IRPP / retenues sur salaires | structuré+RAG | `ref` + `rag_legal` | CGI (officiel) | publique | 🟠 | RH |
| ERP / `finance` | Flux bancaires/MoMo (données client) | live | connecteurs | Connector Framework | — | 🟢 (méca) | FISCAL |
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

### 🟠 Sources officielles identifiées (téléchargement direct)
- **CGI CG (fiscal)** : `finances.gouv.cg` — *Code Général des Impôts, Tome 1* (PDF officiel) ; **Loi de Finances 47-2024** (30/12/2024). Recueil fiscal `unicongo.cg` (à jour LF 2023).
- **Code du travail + décrets + conventions étendues** : Journal Officiel en ligne `sgg.cg` (Loi 1975-45, décret 2006-89…).
- **SMIG** : 70 400 FCFA/mois (2025) ; SMAG distinct (agricole) — fixés par décret.

### 🟠 Jurisprudence & doctrine (couche précédent — cf. §3ter)
- **OHADA-CCJA** : famille de datasets HF `Maathis-com` — *Court Decisions Corpus* (~4 059 décisions structurées) + *Legal Knowledge Graph* (relations), reliés au corpus législatif déjà retenu (licence à confirmer sur la fiche).
- **`ohada.com/jurisprudence`** : ~4 127 décisions (national + CCJA), dont ~1 147 CCJA, téléchargement libre (conditions de réutilisation à vérifier).
- **`juricaf.org`** (AHJUCAF) : base francophone, ~1 325 décisions CCJA, accès libre.

### 🔴 À sourcer (côté utilisateur, contacts officiels)
CIM-10 (OMS, libre), LNME (DPML), **conventions collectives sectorielles** par branche (pétrole/gaz, BTP, commerce — extraction PDF), barèmes **CNSS** + **CIPRES** (prévoyance), Code des marchés publics (ARMP), **jurisprudence Cour Suprême CG** (chambres sociale/civile/commerciale), doctrine/rescrits **DGID**.

---

## 3bis. Décisions d'architecture (peaufinage 2026-06-20)

### 3bis.1 Compta = moteur **hybride** (structuré faisant autorité + RAG d'interprétation)
Décision : **ne pas confier le plan de comptes au RAG.** Le RAG textuel est probabiliste — inadapté à une donnée qui doit être **exacte et déterministe** (un numéro de compte ne s'« interprète » pas).

| Brique | Mécanisme | Rôle |
|--------|-----------|------|
| **Plan de comptes SYSCOHADA** | **table relationnelle de référence** (schéma `ref`) + dictionnaire de codes figé en mémoire | source de vérité : existence d'un compte, classe (1-8), nature, libellé normalisé |
| **Moteur de validation** | logique **déterministe** (pas de LLM) | contrôle d'équilibre (Σdébit = Σcrédit), cohérence classe/sens, comptes autorisés |
| **RAG (AUDCIF + CGI)** | retrieval texte | **uniquement** l'interprétation : « cette écriture est-elle conforme ? quel traitement fiscal ? » + citations |

→ Le sous-agent Compta **n'invente jamais** un compte : il le **lit** dans la table de référence ; le LLM/RAG ne sert qu'à expliquer/justifier (interprétation, conformité). Même principe pour les **barèmes** fiscaux et de paie (structurés `ref`, pas RAG).

### 3bis.2 RH = périmètre élargi (au-delà du Code du travail + CNSS)
La paie/conformité RH en RC mobilise plusieurs corpus, à séparer en structuré vs RAG :
- **RAG (texte)** : Code du travail 1975-45 + décrets, conventions collectives **sectorielles**, droits sociaux.
- **Structuré (`ref`)** : SMIG/SMAG, grilles conventionnelles, cotisations **CNSS** + **CIPRES**, barème **IRPP/retenues sur salaires** (CGI).
→ Un bulletin de paie correct = calcul **déterministe** (barèmes structurés) + justification **RAG** (base légale citée). Jamais l'inverse.

### 3bis.3 Consultation documentaire (« ERP intelligent » — UX)
Oui : l'utilisateur final doit pouvoir **consulter directement** les Actes Uniformes, conventions, CGI, etc. — pas seulement recevoir des réponses d'agents.

- **Capacité** : recherche + navigation + lecture d'articles sources avec citation, **par-dessus le même corpus RAG** déjà ingéré (réutilise `rag/retrieval.py`).
- **Exposition** : endpoint lecture seule type `/v1/kb/search` + `/v1/kb/document/{id}`, **profil `box`** (le client consulte SON corpus), filtré par tags RBAC (`country`, `module`, `tenant`).
- **Double emploi du corpus** : (a) ancrage des agents, (b) consultation humaine directe → un seul corpus, deux usages.
- **Statut** : capacité produit à planifier comme **chantier dédié** (après les agents ERP) ; n'ajoute pas de donnée, seulement une surface d'accès.

## 3ter. Couche jurisprudence & pratique (précédents)

Objectif : que le système ne soit pas **uniquement théorique** (le texte de loi) mais aussi **appliqué** (comment juges/administration l'interprètent réellement). Deux origines :

### A. Jurisprudence externe (disponible maintenant — surtout droit)
- **Quoi** : arrêts **CCJA** (OHADA), décisions nationales (Cour Suprême CG), doctrine administrative/rescrits DGID.
- **Valeur** : ancre les réponses sur la pratique réelle (ex. comment la CCJA tranche une cession de parts litigieuse), pas seulement l'article.
- **Sources** (cf. §3) : HF OHADA-CCJA (~4 059 décisions), `ohada.com` (~4 127), `juricaf.org` (~1 325 CCJA).

### B. Expérience opérationnelle (s'accumule après déploiement — tous domaines)
- **Quoi** : cas réels traités + feedback validé (couche 3). C'est là que la **pratique santé/ERP** se constitue (la jurisprudence n'existe que pour le droit ; en santé/compta l'« expérience » vient des cas validés en production).
- **Lien** : alimente l'enrichissement corpus puis, à terme, le fine-tuning (§4).

### Discipline indispensable (sinon danger)
Une décision **n'est pas une norme** :
- **Tagging distinct** : `type:jurisprudence` / `type:doctrine` vs `type:texte_legal` ; + `juridiction`, `date`, `reference`.
- **Statut temporel** : une jurisprudence peut être isolée, confirmée, ou faire l'objet d'un **revirement** → privilégier le récent/confirmé, **toujours citer** la décision (réf. + date).
- **Hiérarchie** : en cas de conflit, le **texte de loi prime** ; la jurisprudence illustre/interprète, ne crée pas la règle.
- **Validation experte** (juriste OHADA) avant production ; **licences** à vérifier avant ingestion + attribution `NOTICE`.

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
| Créer le schéma `ref` (tables de référence structurées : plan de comptes, barèmes) | avec les agents ERP | assistant |
| Construire le JSON/table canonique plan de comptes SYSCOHADA (couche 2) | avec l'agent Compta | assistant (+ validation Droit) |
| Capacité **consultation documentaire** (`/v1/kb/*`, profil box) | chantier dédié, après agents ERP | assistant |
| Ingérer le corpus OHADA HF (CC-BY-4.0) + attribution NOTICE | dès `rag_erp`/`rag_legal` prêts | assistant |
| Sourcer corpus 🔴 (CIM-10, LNME, conventions coll., CNSS/CIPRES) | en parallèle | utilisateur |
| Ingérer la jurisprudence CCJA (HF/ohada.com/juricaf) avec tag `type:jurisprudence` + vérif licence | après corpus législatif | assistant (+ validation juriste) |
| Baseline `eval` (hallucination) après 1ère ingestion réelle | après ingestion | assistant |
| Concevoir la boucle feedback + apprentissage fédéré (PoC) | Phase 4-5 | à planifier |

---

*Roadmap données/connaissance établie le 2026-06-20. Couvre tous les pôles ; sources vérifiées par recherche web le même jour.*
