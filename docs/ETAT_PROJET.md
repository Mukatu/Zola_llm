# ZolaOS — État du projet & archive consolidée

**Date du snapshot** : 2026-06-23
**Objet** : document **faisant autorité** sur l'état courant + **archive** de tout ce qui a été réalisé. Aligne et indexe la documentation existante (ne la remplace pas).
**Dépôts** : public (cœur AGPL) `github.com/Mukatu/Zola_llm` · privé (actifs Polaris) `github.com/Mukatu/Zola_llm-polaris`.

> Vision : plateforme IA **souveraine, locale-first, multi-secteurs/multi-métiers** pour entreprises et administrations d'Afrique centrale. Marché initial : **Congo-Brazzaville** (architecture multi-pays prête). Modèle : **un moteur (orchestrateur multi-agents), deux faces (SaaS + conseil augmenté Polaris)**. Tout est **Llama-3** (8B/70B).
> Positionnement (addendum 2026-06-23) : **hybride vis-à-vis d'Odoo** — couche IA souveraine + **interop ERP** (connecteurs) + **persistance légère** (système de référence scopé). On ne *devient pas* Odoo ; on l'**augmente** et on offre un registre vivant aux clients sans ERP.

---

## 1. Topologie & sécurité (rappel)
- **Zolabox** (client) : données client locales, actifs publics V2.2. **Zolacortex** (cabinet) : overlays + prompts secrets, jamais la donnée client en direct.
- **Zero Trust** : deux apps **isolées** ; unique pont = **mission éphémère** (JWT scopé, chunks RAG **anonymisés**, lecture seule, audités côté client).
- **Licence** : open-core **AGPL v3** (cœur) + composants Polaris **propriétaires non distribués** + double licence commerciale.

## 2. État par couche (côté code)

| Couche | Contenu | Statut |
|--------|---------|--------|
| Socle (Ph.0-1) | Docker Compose, schémas PG cloisonnés + rôles, audit hash-chain, orchestrateur (Router/Planning/Memory), sécurité JWT/API key, guard anti-fallback, observabilité | ✅ |
| RAG (Ph.2) | bge-m3, chunkers spécialisés, 7 loaders, retrieval RBAC, PII redaction (5 politiques), eval framework | ✅ code |
| Sous-agents V2.2 (Ph.2) | Santé (pharmaco), Droit (OHADA, travail, fiscal, admin) | ✅ code |
| Missions Cortex→Box (Ph.3) | JWT mission, `/v1/box/rag/search`, `/v1/cortex/missions`, audit, `MissionClient` (Zero Trust) | ✅ |
| Code Agent (Ph.3) | Pôle Engineering (generate/refactor/debug/review/test) | ✅ |
| Connector Framework (Ph.4 §2.4) | interface unique, auth pluggable, mapping YAML, registry, SDK custom, 8 connecteurs | ✅ |
| ERP back-office (Ph.4) | RH, **Paie** (moteur + verrou barème), Finance, **Comptabilité SYSCOHADA**, Projets ONG | ✅ |
| ERP pilotage opérationnel | **Supply Chain & Stocks**, **Achats**, **Moyens Généraux**, **Secrétariat sociétaire**, **HSE/RSE** | ✅ |
| Extensions | **BI/Pilotage IA**, **Commercial/CRM**, **Marketing** | ✅ |
| **Endpoints déterministes (FE↔BE)** | `/v1/erp/*` (paie, compta/validate, **compta/suggest**, supply, achats, facility, hse, finance), `/v1/crm/analyze`, `/v1/bi/kpis`, `/v1/mkt/audience` | ✅ |
| **Système de référence léger (persistance)** | `store_invoices`, `store_journal_entries`, `store_stock_items` + repository + migrations Alembic (0005, 0006) | ✅ partiel (voir §3bis) |
| **Compta IA-native** | **clôture continue** (réconciliation temps réel), **balance vivante** des comptes, **auto-catégorisation** (libellé → compte SYSCOHADA, déterministe) | ✅ |
| Personnalisation | config par tenant (`core/personalization.py`) + `GET`/`PUT /v1/config` | ✅ |
| Overlays Polaris (privé) | **19 overlays** d'audit (mode mission) couvrant tous les pôles | ✅ |
| **Frontend (Web PWA)** | FE-1→FE-4 : socle nav config, **~14 écrans riches** + écran générique, **PWA offline** (service worker), **Paramètres** (PUT config), **cockpit Zolacortex** (missions), Vitest | ✅ |

**Principe transverse tenu partout** : **déterministe d'abord** (chiffres/règles en code), **LLM pour interpréter/rédiger** ; forecasting ML hors périmètre (brique dédiée future).

## 3. Inventaire des capacités (par déploiement — frontière de confiance)

| Capacité | Pôle | Déploiement | Moteur | Écran |
|----------|------|-------------|:--:|:--:|
| Assistant (orchestrateur) | — | box + cortex (isolés) | ✅ | ✅ |
| Pharmacologie (+ diagnostic, cas) | Santé | box | ✅/⏳ | générique |
| OHADA / Travail / Fiscal / Administratif | Droit | box | ✅ | ✅ riche (rédaction) |
| Code Agent | Engineering | box + cortex (isolés) | ✅ | ✅ riche (éditeur/diff) |
| RH · Paie · Finance · Compta · Projets ONG | ERP | box | ✅ | ✅ (Paie/Compta/Finance riches) |
| Supply · Achats · Moyens Généraux · Secrétariat · HSE | ERP | box | ✅ | ✅ riches (sauf Secrétariat=générique) |
| Registre & clôture vivante | ERP | box | ✅ | ✅ riche (persisté) |
| Pilotage / BI | BI | box + cortex (isolés) | ✅ | ✅ riche (dashboard) |
| Commercial / CRM | Commercial | box | ✅ | ✅ riche (kanban) |
| Marketing | Marketing | box | ✅ | ✅ riche (consentement) |
| Reporting bailleurs (+ conformité, audit interne) | GRC | box | ⚠️ partiel | générique |
| Scoring crédit · KYC | Fintech | box | ❌ | générique |
| Cyber-défense | Cyber | box | ❌ | générique |
| Langues (Lingala/Kituba) | Pôle K | box + cortex | ⏳ | i18n prêt (dict à fournir) |
| 19 overlays d'audit (mission) | tous | **cortex** (privé) | ✅ | cockpit |

## 3bis. Système de référence léger — état de la persistance ⭐

Trois couches par métier : **Moteur** (calcul déterministe) · **Écran** (UI) · **Persistance** (stockage = ce qui nous rapproche d'Odoo).
La persistance ne couvre **aujourd'hui que 3 entités** ; les autres métiers ont moteur + écran mais **sans mémoire** (données fournies à la requête).

| # | Métier | Moteur | Écran | **Persistance** | Plus-value de la persistance | Prévu |
|---|---|:--:|:--:|:--:|---|---|
| 1 | Compta — Écritures | ✅ | ✅ | ✅ `store_journal_entries` | Grand livre + **balance vivante** | lettrage analytique |
| 2 | Finance / Trésorerie | ✅ | ✅ | ⚠️ factures oui, transactions bancaires non | Solde réel, **clôture continue** | persister relevés bancaires |
| 3 | Facturation / Registre | ✅ | ✅ | ✅ `store_invoices` | Encours clients, relances | avoirs, échéancier |
| 4 | Supply Chain / Stocks | ✅ | ✅ | ✅ `store_stock_items` | Stock réel, réappro auto | mouvements (entrées/sorties), lots |
| 5 | Achats / Procurement | ✅ | ✅ | ❌ | Registre fournisseurs + historique | `Supplier` + `PurchaseOrder` |
| 6 | RH | ✅ | générique | ❌ | Registre des employés + contrats | `Employee` + `Contract` |
| 7 | Paie | ✅ | ✅ | ❌ | Historique des bulletins | `Payslip` (après RH) |
| 8 | CRM / Commercial | ✅ | ✅ | ❌ | **Pipeline réel** suivi dans le temps | `Customer`+`Opportunity`+`Quote` |
| 9 | BI / Pilotage | ✅ | ✅ | N/A (agrège) | KPIs sur **données réelles** stockées | brancher sur le store |
| 10 | Marketing | ✅ | ✅ | ❌ | Base contacts + journal consentement | `MarketingContact`+`Campaign` |
| 11 | Moyens Généraux / Facility | ✅ | ✅ | ❌ | Registre des actifs + échéancier | `Asset`+`Echeance` |
| 12 | HSE / RSE | ✅ | ✅ | ❌ | Registre des risques | `Risque`+`Incident` |
| 13 | Secrétariat sociétaire | ✅ | générique | ❌ | Registre mandats, AG/PV | `Mandat`+`Resolution` |
| 14 | Projets ONG | ✅ | générique | ❌ | Budgets bailleurs, ventilation | `Projet`+`LigneBudget` |
| 15-17 | GRC (conformité, audit, reporting) | ⚠️ | générique | ❌ | Registres obligations/constats/rapports | pôle GRC à compléter |
| 18-19 | Fintech (scoring, KYC) | ❌ | générique | ❌ | Demandes, dossiers KYC | **pôle non construit** |

> **Compte honnête** : persistance réelle = **3 entités / ~19 métiers**. Le socle (`StoreBase` + repository + migrations + tests SQLite) est posé : **étendre aux autres entités est mécanique**, pas une refonte. Domaines **génératifs** (Santé/Droit/Code/Cyber) = hors périmètre persistance (conseil, pas registre).
> **Plus-value globale** : sans persistance = conseiller/calculateur ; **avec** = système de gestion (façon Odoo) **+ couche IA souveraine** → chaque métier tient un **registre vivant** que l'IA réconcilie et pilote en continu.

## 4. Qualité
- **Backend** : **243 tests verts**, 0 échec, 3 désélectionnés (`integration`/`eval`). Image `zolaos:dev-test` (Python 3.12).
- **Frontend** : `tsc --noEmit` + `eslint` + **Vitest (5)** + `next build` **OK** (Next 14.2.35).
- **CI assainie (2026-06-23)** : versions **épinglées** (`ruff==0.7.4`, `black==24.10.0`, `mypy==1.13.0`) → CI déterministe ; **black + ruff + mypy verts** ; job CI **frontend** (typecheck+lint+test+build). *La CI lint n'avait jamais été verte avant (dette de fond résorbée).*
- **Étanchéité dépôts** vérifiée à chaque commit (aucun actif Polaris ni secret dans le public).

## 5. Index de la documentation (alignement)

**Plans (faisant autorité)** : `ZOLAOS_MASTER_PLAN_V2.md` (V2.2 canonique). Addenda : `..._V3_POLARIS_ADDENDUM.md`, `..._ADDENDUM_BI_COMMERCIAL_MARKETING.md`, `..._ADDENDUM_PILOTAGE_OPERATIONNEL.md`, `..._ADDENDUM_UX_PERSONNALISATION.md`, **`..._ADDENDUM_PERSISTANCE_LEGERE.md`** (positionnement Odoo + persistance + compta IA-native).

**Rapports de phase** : `docs/PHASE_1..4_REPORT.md`, `docs/PHASE_2_EXIT_REPORT.md`.

**Stratégie & conception** : `docs/PRODUCT_STRATEGY.md`, `docs/UX_DESIGN_SPEC.md`, `docs/LEGAL_TASK_MODES.md`, `docs/DATA_KNOWLEDGE_ROADMAP.md`.

**Roadmaps de chantier** : **`docs/PERSISTENCE_ROADMAP.md`** (plan d'action persistance par métier — chantier #1), **`docs/SIRH_ROADMAP.md`** (SIRH 3 piliers : recrutement / admin du personnel / développement-GPEC), `docs/CONNECTOR_FRAMEWORK_ROADMAP.md`, `docs/ERP_AGENTS_ROADMAP.md`, `docs/BI_ROADMAP.md`, `docs/CRM_ROADMAP.md`, `docs/MARKETING_ROADMAP.md`, `docs/FRONTEND_ROADMAP.md`. Connecteurs : `docs/CONNECTORS.md`. Front : `frontend/README.md`.

## 6. Archive — chronologie des livraisons (dépôt public)

| Bloc | Commits clés |
|------|--------------|
| Init + sortie Phase 2 | `0f10189` init AGPL · `d8888d7` exit report |
| Connector Framework · Données | `415e062` · `1d708ae`→`549615b` |
| ERP back-office + pilotage | `af75462` RH · `24136bf` Paie · `2b21f44` Compta · `278dec4` Supply · `76fc70d` Achats · `008d581` Facility · `33832da` HSE |
| Extensions BI/CRM/Marketing | `e155706` BI · `5196778` CRM · `f62f8ed` Marketing |
| UX, perso, /v1/config | `b2f2c19` · `27e1412` · `347dc64`/`bd46afa` |
| Frontend FE-1→FE-4 | `81ecd8a` FE-1 · `6eddc55` FE-2 · écrans phares + data + génératif · FE-3 (offline/Paramètres) · `1bd8715` FE-4 cockpit cortex · `07f8627` Vitest+auth |
| **Persistance + compta IA-native** | `de476ea` P1 (Factures + clôture continue) · `22eccbd` P1b (écran Registre) · `16d3c1b` P2 (Écritures + Stocks) · `8edc431` Front P2 (balance vivante) · `6612f3a` auto-catégorisation |
| **Positionnement & CI** | `9356f46` addendum Odoo/persistance · `01abba5` assainissement CI (black/ruff/mypy verts, versions épinglées) |

Dépôt privé Polaris : init + 19 overlays + formatage (`13069d7`).

## 7. Chantiers ouverts

| # | Sujet | Type |
|---|-------|------|
| 1 | **Généraliser la persistance** — plan d'action détaillé par métier : **`docs/PERSISTENCE_ROADMAP.md`** (P2b Commercial → P2c Achats/RH/Paie → P2d Facility/HSE/Marketing → P2e Finance/Secrétariat/ONG → P2f Documents → P3) | backend + FE |
| 2 | **Pôles manquants** : **Fintech** (scoring/KYC + MoMo/Airtel), **GRC complet**, **Cyber**, **Pôle K** (langues) | backend |
| 3 | **P3 intelligence** : BI sur le store (KPIs réels), **prévision de trésorerie** (brique ML), multi-devise | backend |
| 4 | **Sortie réelle Phase 2** : sourcer corpus (CIM-10, OHADA, CGI, Code travail, LNME), valider **barèmes paie + plan de comptes**, baseline `eval`, pilotes | terrain (utilisateur) |
| 5 | Schémas RAG dédiés `rag_erp` / `rag_grc` (sortir des placeholders `rag_legal`) | backend |
| 6 | Brancher l'**auth** front en démo · i18n Lingala/Kituba · résorber la **dette typage** mypy (remonter en strict total) | FE + qualité |
| 7 | **Apprentissage fédéré** (PoC, gradients chiffrés inter-Box) | R&D |

---

*Snapshot consolidé au 2026-06-23. Met en cohérence et indexe la documentation existante ; sert d'archive de l'avancement. La persistance (système de référence léger) couvre 3 entités sur ~19 métiers — généralisation = chantier ouvert #1.*
