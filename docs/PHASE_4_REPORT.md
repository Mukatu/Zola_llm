# ZolaOS — Rapport de progression Phase 4 (Pôles étendus + couverture overlays Polaris)

**Date** : 2026-06-17
**Statut global** : Phase 4 **amorcée**. Premiers sous-agents des pôles ERP / GRC et du module Droit administratif livrés ; couverture **overlay Polaris complète sur les 8 pôles** (doctrine « un overlay par pôle, sans exception » respectée). Schémas RAG dédiés (`rag_erp`, `rag_grc`) et sourcing corpus restent à faire.
**Références** :
- Rapport Phase 3 : [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md)
- Addendum Polaris : [`../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md`](../ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md)

> Ce document complète `PHASE_3_REPORT.md`. Phase 4 n'est pas close : ce rapport acte ce qui est livré côté code et liste explicitement ce qui reste.

---

## 1. Vue d'ensemble

| Bloc | Périmètre | Statut |
|------|-----------|--------|
| **Sous-agent Droit administratif CG** | `legal/admin_cg.py` — marchés publics, ARMP, contentieux (Polaris-9) | ✅ code |
| **Sous-agent Projets ONG** | `erp/projets_ong.py` — gestion financière ONG, multi-devises (Polaris-10) | ✅ code |
| **Sous-agent Reporting bailleurs** | `grc/reporting_bailleurs.py` — IATI, PRAG, OECD-DAC (Polaris-10) | ✅ code |
| **Couverture overlays Polaris** | 13 overlays sur 9 fichiers, **8 pôles couverts** | ✅ code |
| **Schémas RAG dédiés** `rag_erp` / `rag_grc` | placeholders sur `rag_legal` pour l'instant | ⏳ à créer |
| **Apprentissage fédéré (PoC)** | Polaris-11 | ⏳ non démarré |
| **Tests** | `test_phase4_subagents.py` (4), `test_polaris_all_overlays.py` (4) | ✅ |

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

**Run vérifié le 2026-06-17 : 117 tests collectés → 114 passés, 0 échec, 3 désélectionnés** (`integration` + `eval`, nécessitent Postgres/Redis/LLM réel). Détail et note build dans [`PHASE_3_REPORT.md`](./PHASE_3_REPORT.md) §7.

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

*Document généré à partir de l'état du repo et de la mémoire au 2026-06-17.*
