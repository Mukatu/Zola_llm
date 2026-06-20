# Feuille de route — BI / Pilotage IA (capacité transversale)

**Date** : 2026-06-21
**Référence** : `ZOLAOS_MASTER_PLAN_ADDENDUM_BI_COMMERCIAL_MARKETING.md` §3.1. S'appuie sur le Connector Framework (livré) et généralise l'agent Finance.
**Engagement** : suivie dans l'ordre BI-1 → BI-3, chaque jalon tracé + tests verts.

---

## Principe directeur (non négociable)
**Les chiffres sont déterministes (calculés en code), le LLM interprète/narre/recommande — il ne calcule jamais.** Forecasting prédictif = brique dédiée (modèles séries temporelles), **hors MVP**.

Trois étages : **données** (Connector Framework, multi-domaines) → **KPIs déterministes** → **couche IA** (insights narratifs, Q&A langage naturel sur les KPIs, recommandations).

---

## Jalon BI-1 — Moteur de KPIs déterministe — **premier**
- `src/zolaos/agents/bi/kpi.py` : `KpiValue` + fonctions **pures** cross-domaines à partir des modèles canoniques (Invoice/BankTransaction/Employee) et des sorties paie :
  - **Commercial/Finance** : chiffre d'affaires, achats, marge brute, encours clients, DSO, trésorerie nette.
  - **RH** : effectif, masse salariale.
- `compute_kpis(...)` assemble les KPIs disponibles selon les données fournies. Tests exacts.

## Jalon BI-2 — Agent BI (couche IA)
- `src/zolaos/agents/bi/agent.py` : `BIAgent` :
  - `compute(...)` / `compute_from_connector(...)` → KPIs déterministes (délègue à BI-1, via le Connector Framework).
  - `synthesize(kpis)` → **synthèse narrative** (insights + recommandations) ; le LLM **narre les chiffres fournis**, sans recalcul.
  - `answer(question, kpis)` → **Q&A en langage naturel SUR le set de KPIs calculés** (le LLM sélectionne/explique les KPIs pertinents).
- `agents/prompts/bi/pilotage.md` versionné. Tests (y compris : le LLM reçoit bien les chiffres calculés).

## Jalon BI-3 — Overlay Polaris + clôture
- Overlay Polaris **Pilotage augmenté** (dépôt privé, profil cortex — doctrine overlay par sous-agent).
- `docs/` : doc d'usage + maj statut. Tests d'ensemble sans régression.

---

## Critères de sortie
- KPIs cross-domaines calculés **en code**, testés exacts.
- `BIAgent` : synthèse + Q&A langage naturel **sur les KPIs** (le LLM ne calcule pas), branché sur les connecteurs.
- Overlay Polaris présent. Aucune régression.

## Hors périmètre (clarté, pas oubli)
- **Forecasting prédictif** (séries temporelles) → brique dédiée ultérieure.
- **Text-to-SQL / requêtes arbitraires** sur la base → écarté (risque correction/sécurité) ; le Q&A porte sur le **set de KPIs calculés**, pas un accès libre aux données.
- Pôles **Commercial/CRM** et **Marketing** → chantiers suivants de l'addendum.

---

## Statut

| Jalon | État |
|-------|------|
| BI-1 moteur KPIs déterministe | ✅ livré (8 KPIs cross-domaines, tests exacts) |
| BI-2 agent BI (IA) | ✅ livré (synthèse + Q&A sur KPIs + connecteurs) |
| BI-3 overlay + clôture | ✅ overlay privé `ZolaCortex-Pilotage` + 160 tests verts |

> **BI / Pilotage IA bouclé (2026-06-21).** Prochaines extensions de l'addendum : **Commercial/CRM**, puis **Marketing**.

*Feuille de route établie et exécutée le 2026-06-21.*
