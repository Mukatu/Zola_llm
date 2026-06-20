# ZolaOS — Rapport de progression Phase 4 (Pôles étendus + couverture overlays Polaris)

**Date** : 2026-06-17 · **mise à jour 2026-06-21**
**Statut global** : Phase 4 — **Connector Framework livré** + **ERP back-office bouclé côté code** (RH, paie déterministe, Finance, Comptabilité/Fiscalité). Couverture **overlay Polaris complète sur les 8 pôles**. Restent : schémas RAG dédiés (`rag_erp`/`rag_grc`), sourcing corpus, et les extensions de périmètre BI/Commercial/Marketing (capturées, codage à venir).
**Références** :
- Rapport Phase 3 : [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md)
- Addendum Polaris : [`../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md)
- Connector Framework : [`CONNECTOR_FRAMEWORK_ROADMAP.md`](./CONNECTOR_FRAMEWORK_ROADMAP.md)
- ERP : [`ERP_AGENTS_ROADMAP.md`](./ERP_AGENTS_ROADMAP.md) · Données : [`DATA_KNOWLEDGE_ROADMAP.md`](./DATA_KNOWLEDGE_ROADMAP.md) · Modes juridiques : [`LEGAL_TASK_MODES.md`](./LEGAL_TASK_MODES.md)
- Extension de périmètre : [`../ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md`](../ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md)

> Ce document complète `PHASE_3_REPORT.md`. Voir §8 pour la mise à jour 2026-06-21 (Connector Framework + ERP back-office).

---

## 1. Vue d'ensemble

| Bloc | Périmètre | Statut |
|------|-----------|--------|
| **Sous-agent Droit administratif CG** | `legal/admin_cg.py` — marchés publics, ARMP, contentieux (Polaris-9) | ✅ code |
| **Sous-agent Projets ONG** | `erp/projets_ong.py` — gestion financière ONG, multi-devises (Polaris-10) | ✅ code |
| **Sous-agent Reporting bailleurs** | `grc/reporting_bailleurs.py` — IATI, PRAG, OECD-DAC (Polaris-10) | ✅ code |
| **Connector Framework** | `connectors/` — interface unique, auth pluggable, mapping YAML, registry, SDK custom + 8 connecteurs (csv/rest/sql/webhook/odoo/erpnext/soap/sage) | ✅ livré (cf. §8) |
| **Sous-agent RH** | `erp/rh.py` — génératif (docs RH + conformité), corpus travail_cg | ✅ livré |
| **Moteur de paie déterministe** | `erp/payroll.py` — calcul paramétré + verrou de validation (barèmes `ref`) | ✅ livré |
| **Sous-agent Finance** | `erp/finance.py` — anomalies déterministes (connecteurs) + synthèse générative | ✅ livré |
| **Compta & Fiscalité** | `erp/compta.py` — plan de comptes SYSCOHADA `ref` + validation déterministe + RAG interprétation | ✅ livré |
| **Couverture overlays Polaris** | 13 overlays sur 9 fichiers, **8 pôles couverts** | ✅ code |
| **Schémas RAG dédiés** `rag_erp` / `rag_grc` | placeholders sur `rag_legal` pour l'instant | ⏳ à créer |
| **Apprentissage fédéré (PoC)** | Polaris-11 | ⏳ non démarré |
| **Tests** | suite complète **152 verts** (dont connectors 15, ERP RH/paie/finance/compta 23) | ✅ |

---

## 2. Nouveaux sous-agents génératifs V2.2

Tous sont des sous-classes de `RAGAgent` (pattern Phase 2 : `retrieve → contexte numéroté → LLM → réponse + citations`), modèle **Llama-3-8B**, `requires_citation=True`.

| Agent | Module | `rag_schema` | `min_confidence` | Spécificité |
|-------|--------|--------------|------------------|-------------|
| `AdminCgAgent` | `legal.admin_cg` | `rag_legal` | 0.60 | Sujet politiquement sensible : `temperature=0.05` (quasi-déterministe), neutralité éditoriale stricte. Sources : Code des marchés publics CG, Lois de Finances, Cour des Comptes, ARMP. |
| `ProjetsOngAgent` | `erp.projets_ong` | `rag_legal` *(placeholder)* | 0.50 | Gestion financière ONG, ventilation bailleur/projet, trésorerie multi-devises. Sources : SYSCOHADA ONG, OECD-DAC, IPSAS, conventions de financement. |
| `ReportingBailleursAgent` | `grc.reporting_bailleurs` | `rag_legal` *(placeholder)* | 0.50 | Rapports bailleurs internationaux (UE, ONU, BM, AFD, USAID), conformité IATI/PRAG. Multi-langue FR+EN (anticipe Pôle K). Sources : IATI, guides PRAG, GAFI. |

> ⚠️ **Placeholder RAG** : `projets_ong` et `reporting_bailleurs` pointent provisoirement sur `rag_legal` faute de schémas `rag_erp` / `rag_grc`. À rebrancher dès la migration dédiée (voir §4).

---

## 3. Couverture overlays Polaris — 8 pôles

Tous les overlays héritent de `PolarisOverlay` (profil **cortex obligatoire**, `response_schema` obligatoire, `requires_citation=True`, inférence locale Cortex — cf. Zero Trust, Phase 3 §4).

| Pôle ZolaOS | Overlay(s) | Nom officiel | Fichier |
|-------------|-----------|--------------|---------|
| Droit (travail) | `ConformiteRhOverlay` | `ZolaCortex-Conformite-RH` | `conformite_rh.py` |
| Droit (fiscal/OHADA) | `FiscalOhadaOverlay` | `ZolaCortex-Fiscal-OHADA` | `fiscal_ohada.py` |
| Droit (OHADA juridique) | `OhadaJuridiqueOverlay` | `ZolaCortex-Audit-Juridique-OHADA` | `ohada_juridique.py` |
| ERP (finance) | `TresorerieOverlay` | `ZolaCortex-Tresorerie` | `tresorerie.py` |
| Santé | `AuditSanteOverlay` | `ZolaCortex-Audit-Sante` | `audit_sante.py` |
| Engineering | `CodeReviewOverlay`, `AuditSecuriteCodeOverlay` | `ZolaCortex-Code-Review`, `ZolaCortex-Audit-Securite-Code` | `code_review.py` |
| Cyber | `CyberDefenseOverlay` | `ZolaCortex-Cyber-Defense` | `cyber_defense.py` |
| GRC | `AuditConformiteOverlay`, `AuditInstitutionnelOverlay`, `ReportingBailleursOverlay` | `ZolaCortex-Audit-Conformite`, `ZolaCortex-Audit-Institutionnel`, `ZolaCortex-Reporting-Bailleurs` | `grc.py` |
| Fintech | `ScoringAuditOverlay`, `KycAuditOverlay` | `ZolaCortex-Scoring-Audit`, `ZolaCortex-KYC-Audit` | `fintech.py` |

**13 overlays, 8 pôles couverts.** La mémoire `project_polaris_overlay_universality.md` (« chaque pôle doit avoir son overlay, sans exception ») et `feedback_overlay_after_subagent.md` (« créer l'overlay dans la foulée du sous-agent ») sont respectées.

Prompts secrets cabinet correspondants sous `agents/prompts/polaris/*.md` (frontmatter `secret: true`, non distribués — Zero Trust).

---

## 4. Ce qui reste pour clore Phase 4 (côté code)

| # | Sujet | Pourquoi |
|---|-------|----------|
| P4.1 | Migration Alembic `rag_erp.documents` + `rag_grc.documents` (HNSW + GIN tags) | Sortir `projets_ong` / `reporting_bailleurs` du placeholder `rag_legal` |
| P4.2 | Rebrancher `rag_schema` des 2 sous-agents ONG/bailleurs sur les nouveaux schémas | Cohérence RBAC + isolation des corpus |
| P4.3 | Chunker spécialisé reporting bailleurs (logframe / ToC) si besoin | Qualité retrieval |
| P4.4 | Apprentissage fédéré — PoC (Polaris-11) | Gradients chiffrés inter-Box (conception) |
| P4.5 | Schémas OUTPUT_FORMAT dédiés par overlay GRC/Fintech (si non encore spécifiques) | Conformité specs cabinet |

---

## 5. Tests Phase 4

| Suite | Tests | Couverture |
|-------|-------|------------|
| `tests/test_phase4_subagents.py` | 4 | instanciation + comportement des 3 nouveaux sous-agents |
| `tests/test_polaris_all_overlays.py` | 4 | instanciation des overlays, garde profil cortex, `response_schema` obligatoire |

**Run vérifié le 2026-06-21 : 155 tests collectés → 152 passés, 0 échec, 3 désélectionnés** (`integration` + `eval`, nécessitent Postgres/Redis/LLM réel). Inclut les suites Connector Framework (`test_connectors.py`, 15) et ERP (`test_erp_rh.py` 3, `test_erp_finance.py` 6, `test_erp_payroll.py` 6, `test_erp_compta.py` 8). Détail et note build dans [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md) §7.

---

## 6. Ce qui bloque encore la *sortie réelle* de Phase 2 (inchangé — non technique)

Le code Phase 2 → 4 est prêt à recevoir des données réelles. Restent à coordonner côté utilisateur :

1. **Sourcing corpus** : CIM-10 (OMS), 9 Actes Uniformes OHADA, Code du travail CG 45/75, CGI CG + dernière Loi de Finances, LNME congolaise (DPML).
2. **Pilotes terrain** : 1er pilote = Polaris lui-même (consultants sur cas test Cortex) + 1 client réel (cabinet d'avocats / polyclinique / PME Brazzaville).
3. **Campagne `pytest -m eval`** contre LLM réel une fois les corpus ingérés → baseline taux d'hallucination (< 5 % in-domain visé).
4. **Experts validateurs** : pharmacien (100 Q/R santé), juriste OHADA (50 cas/module).

KPI de sortie Phase 2 (V2.2 + ajustés Polaris) : hallucination < 5 % in-domain, latence routage p95 < 3 s (e2e Strix Halo accepté ≤ 8 s sans GPU dédié), 3 modules juridiques en production, conformité OUTPUT_FORMAT 100 % des appels overlays, ≥ 1 rapport `.docx` validé sur mission test.

---

## 7. Phases ultérieures (non démarrées)

| Phase | Périmètre |
|-------|-----------|
| 5 | GRC complet + Fintech (au-delà des overlays) |
| 6 | Fintech — scoring crédit / KYC opérationnels |
| 7 | Cyber-défense opérationnelle |
| 8 | Industrialisation |
| 9 | **Pôle K (langues)** — dernier, par décision V2.2 |

---

## 8. Mise à jour 2026-06-21 — Connector Framework + ERP back-office

### 8.1 Connector Framework (§2.4 du plan — était entièrement absent)
Livré intégralement (cf. [`CONNECTOR_FRAMEWORK_ROADMAP.md`](./CONNECTOR_FRAMEWORK_ROADMAP.md)) : interface unique (`list_employees`/`read_invoice`/`push_journal_entry`/`list_bank_transactions`), modèles canoniques, **auth pluggable** (ApiKey/OAuth2/Basic/Certificat/IPAllowlist), **mapping déclaratif YAML**, **registry** + **SDK custom**, et 8 connecteurs (`csv_excel`, `generic_rest`, `generic_sql`, `webhook`, `odoo`, `erpnext` complets ; `generic_soap`/`sage` à dépendance optionnelle). Métriques `zolaos_connector_*`. 15 tests.

### 8.2 Sous-agents ERP (§4.1-4.3 — étaient absents)
Principe : **déterministe d'abord, LLM pour interpréter/rédiger** (cf. [`ERP_AGENTS_ROADMAP.md`](./ERP_AGENTS_ROADMAP.md)).

| Agent | Type | Détail |
|-------|------|--------|
| `RhAgent` (`erp/rh.py`) | génératif RAG | docs RH (CDI/CDD, lettres, notifications) + conformité, ancré travail_cg, citations + garde-fous |
| `PayrollCalculator` (`erp/payroll.py`) | **déterministe** | bulletin paramétré (CNSS/CIPRES/IRPP/SMIG en `ref`) + **verrou de validation** (refus si barèmes non validés) |
| `FinanceAgent` (`erp/finance.py`) | hybride | anomalies **déterministes** (doublons/dépassements/échéances) via connecteurs + synthèse générative |
| `ComptaAgent` (`erp/compta.py`) | hybride | plan de comptes SYSCOHADA `ref` + `JournalValidator` **déterministe** (équilibre/comptes/partie double) + RAG AUDCIF/CGI pour l'interprétation fiscale |

Overlays Polaris correspondants déjà présents (Conformité-RH, Trésorerie, Fiscal-OHADA).

### 8.3 Données & sources (vérifiées)
[`DATA_KNOWLEDGE_ROADMAP.md`](./DATA_KNOWLEDGE_ROADMAP.md) : 3 couches (RAG / référence structurée / auto-amélioration) + **couche jurisprudence/pratique** (CCJA). Sources vérifiées : corpus OHADA HF (CC-BY-4.0), plan de comptes SYSCOHADA, CGI/JO officiels CG. Barèmes paie + plan de comptes seedés **flaggés non validés** (à faire valider par expert).

### 8.4 Extension de périmètre actée
[`../ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md`](../ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md) : ajout de la BI/Pilotage IA (transversal), du pôle Commercial/CRM et du pôle Marketing. **Codage après l'ERP back-office.**

### 8.5 Reste pour la sortie réelle (inchangé, non technique)
Sourcing + validation experts des corpus/barèmes (côté utilisateur), schémas `rag_erp`/`rag_grc` dédiés, pilotes terrain, baseline `eval`.

---

*Document généré à partir de l'état du repo et de la mémoire au 2026-06-17 ; mis à jour le 2026-06-21.*
