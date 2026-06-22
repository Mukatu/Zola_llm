# ZolaOS — État du projet & archive consolidée

**Date du snapshot** : 2026-06-22
**Objet** : document **faisant autorité** sur l'état courant + **archive** de tout ce qui a été réalisé. Aligne et indexe la documentation existante (ne la remplace pas).
**Dépôts** : public (cœur AGPL) `github.com/Mukatu/Zola_llm` · privé (actifs Polaris) `github.com/Mukatu/Zola_llm-polaris`.

> Vision : plateforme IA **souveraine, locale-first, multi-secteurs/multi-métiers** pour entreprises et administrations d'Afrique centrale. Marché initial : **Congo-Brazzaville** (architecture multi-pays prête). Modèle : **un moteur (orchestrateur multi-agents), deux faces (SaaS + conseil augmenté Polaris)**. Tout est **Llama-3** (8B/70B).

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
| ERP back-office (Ph.4) | RH, **Paie** (moteur déterministe + verrou barème), Finance, Comptabilité SYSCOHADA (validation déterministe), Projets ONG | ✅ |
| ERP pilotage opérationnel (addendum) | **Supply Chain & Stocks**, **Achats**, **Moyens Généraux**, **Secrétariat sociétaire**, **HSE/RSE** | ✅ |
| Extensions (addendum) | **BI/Pilotage IA**, **Commercial/CRM**, **Marketing** | ✅ |
| Personnalisation | config par tenant (`core/personalization.py`) + `GET /v1/config` | ✅ |
| Overlays Polaris (privé) | **19 overlays** d'audit (mode mission) couvrant tous les pôles | ✅ |
| Frontend (Web PWA) | FE-1 socle (Next 14 + TS + Tailwind, nav pilotée par config) + FE-2 (écran de capacité complet pour toutes les capacités) | ✅ socle |

**Principe transverse tenu partout** : **déterministe d'abord** (chiffres/règles en code), **LLM pour interpréter/rédiger** ; forecasting ML hors périmètre (brique dédiée future).

## 3. Inventaire des capacités (par déploiement — frontière de confiance)

| Capacité | Pôle | Déploiement | Statut |
|----------|------|-------------|--------|
| Assistant (orchestrateur) | — | box + cortex (isolés) | ✅ |
| Pharmacologie (+ diagnostic, cas) | Santé | box | ✅ / ⏳ |
| OHADA / Travail / Fiscal / Administratif | Droit | box | ✅ |
| Social/Civil/Pénal/PI-OAPI/Données | Droit | box | ⏳ |
| Code Agent | Engineering | box + cortex (instances isolées) | ✅ |
| RH · Paie · Finance · Comptabilité · Projets ONG | ERP | box | ✅ |
| Supply Chain · Achats · Moyens Généraux · Secrétariat · HSE/RSE | ERP | box | ✅ |
| Pilotage / BI | BI | box + cortex (isolés) | ✅ |
| Commercial / CRM | Commercial | box | ✅ |
| Marketing | Marketing | box | ✅ |
| Reporting bailleurs (+ conformité, audit interne) | GRC | box | ✅ / ⏳ |
| Scoring crédit · KYC | Fintech | box | ⏳ |
| Cyber-défense | Cyber | box | ⏳ |
| Langues (Lingala/Kituba) | Pôle K | box + cortex | ⏳ |
| 19 overlays d'audit (mission) | tous | **cortex** (privé) | ✅ |
| Router · Planning · Mémoire | — | interne (sans écran) | ✅ |

## 4. Qualité
- **Backend** : **220 tests verts**, 0 échec, 3 désélectionnés (`integration`/`eval`, nécessitent Postgres/Redis/LLM réel). Image `zolaos:dev-test` (Python 3.12).
- **Frontend** : `tsc --noEmit` + `next build` **OK** (Next 14.2.35, correctif sécurité).
- **Étanchéité dépôts** vérifiée à chaque commit (aucun actif Polaris ni secret dans le public).

## 5. Index de la documentation (alignement)

**Plans (faisant autorité)** :
- `ZOLAOS_MASTER_PLAN_V2.md` (V2.2 — cahier des charges canonique) ; `ZOLAOS_MASTER_PLAN.md.md` (origine, périmé).
- Addenda : `..._V3_POLARIS_ADDENDUM.md` (Polaris/Zero Trust/licence), `..._ADDENDUM_BI_COMMERCIAL_MARKETING.md`, `..._ADDENDUM_PILOTAGE_OPERATIONNEL.md`, `..._ADDENDUM_UX_PERSONNALISATION.md`.

**Rapports de phase** : `docs/PHASE_1..4_REPORT.md`, `docs/PHASE_2_EXIT_REPORT.md`.

**Stratégie & conception** : `docs/PRODUCT_STRATEGY.md` (un moteur, deux faces), `docs/UX_DESIGN_SPEC.md`, `docs/LEGAL_TASK_MODES.md`, `docs/DATA_KNOWLEDGE_ROADMAP.md`.

**Roadmaps de chantier** : `docs/CONNECTOR_FRAMEWORK_ROADMAP.md`, `docs/ERP_AGENTS_ROADMAP.md`, `docs/BI_ROADMAP.md`, `docs/CRM_ROADMAP.md`, `docs/MARKETING_ROADMAP.md`, `docs/FRONTEND_ROADMAP.md`. Usage connecteurs : `docs/CONNECTORS.md`. SDK : `src/zolaos/connectors/custom_sdk/README.md`. Front : `frontend/README.md`.

## 6. Archive — chronologie des livraisons (dépôt public)

| Bloc | Commits clés |
|------|--------------|
| Init + sortie Phase 2 | `0f10189` init AGPL · `d8888d7` exit report |
| Connector Framework | `415e062` |
| Données/connaissance | `1d708ae` → `549615b` (couches, compta hybride, jurisprudence) |
| ERP back-office | `af75462` RH · `afb656e` Finance · `24136bf` Paie · `2b21f44` Compta · `e15f66b` clôture |
| Addendum + extensions | `2657b4f` addendum · `e155706`/`d6a0870` BI · `5196778`/`f67f792` CRM · `f62f8ed` Marketing |
| UX & stratégie | `b2f2c19` perso+/v1/config · `27e1412` UX spec · `347dc64`/`bd46afa` corrections (écrans/Zero Trust) |
| Pilotage opérationnel | `278dec4` Supply · `76fc70d` Achats · `008d581` Facility · `054667e` Secrétariat · `33832da` HSE · `caa3a60` clôture |
| Frontend | `81ecd8a` FE-1 socle · `6eddc55` FE-2 écrans |

Dépôt privé Polaris : init + 19 overlays (Conformité-RH, Fiscal-OHADA, Audit-Juridique-OHADA, Trésorerie, Audit-Santé, Code-Review, Audit-Sécurité-Code, Cyber-Defense, Audit-Conformité, Audit-Institutionnel, Reporting-Bailleurs, Scoring-Audit, KYC-Audit, Pilotage, Audit-Commercial, Audit-Marketing, Audit-SupplyChain, Audit-Achats, Audit-HSE-Gouvernance).

## 7. Chantiers ouverts

| # | Sujet | Type |
|---|-------|------|
| 1 | **Sortie réelle Phase 2** : sourcer corpus (CIM-10, OHADA, CGI, Code travail, LNME), valider barèmes paie + plan de comptes, baseline `eval`, pilotes | terrain (utilisateur) |
| 2 | Agents **GRC complet, Fintech (scoring/KYC + MoMo/Airtel), Cyber, Pôle K** | backend |
| 3 | **Schémas RAG dédiés** `rag_erp` / `rag_grc` (sortir des placeholders `rag_legal`) | backend |
| 4 | **FE↔BE** : exposer les moteurs déterministes en endpoints `/v1` (Paie, Compta, Supply, Finance, CRM, BI…) pour les écrans riches | FE+BE |
| 5 | **FE-3** (KB, Documents, Paramètres, offline/service worker, i18n) · **FE-4** Zolacortex (cockpit missions) | frontend |
| 6 | **Apprentissage fédéré** (PoC, gradients chiffrés inter-Box) | R&D |

---

*Snapshot consolidé au 2026-06-22. Met en cohérence et indexe la documentation existante ; sert d'archive de l'avancement.*
