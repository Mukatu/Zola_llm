# Prompts versionnés

Ce dossier contient tous les **system prompts** utilisés par les sous-agents et méta-agents de ZolaOS. Les prompts sont du **code critique** et suivent les mêmes règles de versioning que le reste du codebase.

Format et conventions : voir [`CONTRIBUTING.md`](../../CONTRIBUTING.md#versioning-des-prompts).

## Structure cible (alimentée au fil des phases)

| Pôle / Méta-agent | Fichiers prévus                                                   | Phase |
|-------------------|-------------------------------------------------------------------|-------|
| Routeur           | `router.md`                                                       | 1     |
| Méta-agents       | `meta/memory.md`, `meta/planning.md`, `meta/supervision.md`       | 1     |
| Santé             | `health/pharmacology.md`                                          | 2     |
| Droit             | `legal/ohada.md`, `legal/labor_cg.md`, `legal/tax_cg.md`          | 2     |
| Droit (suite)     | `legal/social_cg.md`, `legal/civil_cg.md`, `legal/criminal_cg.md`, `legal/ip_oapi.md`, `legal/data_cg.md` | 4 |
| Code Agent        | `engineering/code_agent.md`                                       | 3     |
| ERP               | `erp/hr.md`, `erp/finance.md`, `erp/accounting.md`                | 4     |
| GRC               | `grc/audit.md`, `grc/risk.md`, `grc/reporting.md`, `grc/watch.md` | 5     |
| Fintech           | `fintech/scoring.md`, `fintech/kyc.md`                            | 6     |
| Cyber             | `cyber/audit.md`, `cyber/anomaly.md`, `cyber/hardening.md`        | 7     |
| Pôle K            | `k/translation.md`                                                | 9     |
