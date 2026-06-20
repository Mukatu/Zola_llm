# ZolaOS — Addendum de périmètre : BI/Pilotage IA, Commercial/CRM, Marketing

**Date** : 2026-06-20
**Statut** : addendum **stratégique** validé. **Complète** `ZOLAOS_MASTER_PLAN_V2.md` (V2.2) et `ZOLAOS_MASTER_PLAN_V3_POLARIS_ADDENDUM.md` — ne les remplace pas.
**Décision** : capturer maintenant, **coder après l'ERP back-office** (Compta + clôture ERP).

---

## 1. Constat (trou dans le plan)

Le cahier des charges V2.2 définit un **ERP volontairement back-office** (RH, Finance, Comptabilité/Fiscalité). Sont **absents du plan** :
- **Commercial / CRM / ventes** — aucun pôle ni module.
- **Marketing** — aucun pôle ni module.
- **BI / analytics transversale** — seul existe du reporting *par domaine* (synthèse Finance §4.2, reporting réglementaire GRC §5.3) ; **pas** de couche d'aide au pilotage cross-métiers, ni de « BI version IA ».

Cet addendum comble ces trois manques comme **extensions** (le reste du plan est inchangé).

---

## 2. Principe directeur (hérité de l'ERP)

**Déterministe d'abord, IA pour l'interprétation.** Les **chiffres/KPIs sont calculés en code** (exacts, traçables) ; le **LLM interprète, interroge en langage naturel, raconte, recommande** — il ne calcule jamais les agrégats. (Même règle que l'agent Finance, qui est déjà le 1er étage de la BI.)

---

## 3. Nouveaux périmètres

### 3.1 Capacité transversale — **BI / Pilotage IA**
Couche analytique au-dessus de tous les pôles (comme GRC est transversal).

| Étage | Mécanisme |
|------|-----------|
| Données | Connector Framework (multi-domaines : ventes, paie, factures, banque…) |
| **KPIs déterministes** | calcul en code : CA, marge, masse salariale, DSO, trésorerie, turnover RH, taux de conversion… |
| **IA** | requêtes en **langage naturel** sur les données, **insights narratifs**, détection de tendances/anomalies, **recommandations** |

- **Prévisionnel (forecasting)** : isolé comme brique **avancée** (modèles séries temporelles dédiés), **pas** confié au LLM.
- Réutilise et **généralise l'agent Finance**. RBAC par tags + profils box/cortex respectés.
- Overlay Polaris : tableau de bord de pilotage augmenté (mode mission).

### 3.2 Pôle **Commercial / CRM & Ventes**
- Clients/prospects, **pipeline/opportunités**, **devis → factures** (intègre la Compta §4.3), **relances** automatiques, **scoring de leads**.
- Données = opérationnelles client (via connecteurs) — peu de corpus externe.
- PII : politique `FISCAL`/`GENERIC` selon les données. Overlay Polaris : audit commercial/performance.

### 3.3 Pôle **Marketing**
- **Segmentation** clientèle, **campagnes**, **génération de contenu** (offres, emailing, posts) — forte valeur **générative LLM**.
- Conformité **Loi 29-2019** (données personnelles) impérative (consentement, finalité). Overlay Polaris : stratégie/contenu.

---

## 4. Impact roadmap (séquence décidée)

Ordre : **finir l'ERP back-office d'abord**, puis ces extensions.

1. **(en cours)** ERP back-office : RH ✅, Finance ✅, RH-2 paie ✅, **Compta & Fiscalité** 🔜, clôture ERP.
2. **BI / Pilotage IA** (généralise Finance) — 1re extension (dépend des données ERP en place).
3. **Commercial / CRM & Ventes** (s'appuie sur Compta + connecteurs).
4. **Marketing** (génératif + conformité données perso).

Chaque nouveau sous-agent reçoit son **overlay Polaris dans la foulée** (doctrine projet).

---

## 5. Impact sur les pôles

V2.2 = 8 pôles. Cet addendum ajoute **2 pôles métier** (Commercial, Marketing) + **1 capacité transversale** (BI/Pilotage, à l'instar de GRC). Cohérent avec la doctrine « on ajoute, on n'enlève rien ». Le marché initial (RC/Brazzaville) et la priorité Santé/Droit restent inchangés.

---

## 6. Données (lien)

Mise à jour à intégrer dans [`docs/DATA_KNOWLEDGE_ROADMAP.md`](./docs/DATA_KNOWLEDGE_ROADMAP.md) :
- Commercial/Marketing = surtout **données opérationnelles client** (connecteurs), pas de gros corpus externe.
- BI = pas de données propres : **consomme** celles des autres pôles.
- Marketing : encadrement **Loi 29-2019** (PII) au cœur.

---

## 7. Hors périmètre (clarté)

- Forecasting prédictif avancé (modèles dédiés) — brique ultérieure, pas le LLM.
- Connecteurs Mobile Money — Phase 6 Fintech.
- Le codage de ces extensions ne démarre **qu'après** la clôture de l'ERP back-office.

---

## 8. Statut de réalisation (2026-06-21) — ✅ 3/3 livrées

| Extension | État | Livrables |
|-----------|------|-----------|
| BI / Pilotage IA | ✅ | `agents/bi/` (KPIs déterministes + agent synthèse/Q&A) + overlay privé `ZolaCortex-Pilotage` — [`docs/BI_ROADMAP.md`](./docs/BI_ROADMAP.md) |
| Commercial / CRM & Ventes | ✅ | `agents/crm/` (pipeline/scoring/relances/devis→facture + agent) + overlay privé `ZolaCortex-Audit-Commercial` — [`docs/CRM_ROADMAP.md`](./docs/CRM_ROADMAP.md) |
| Marketing | ✅ | `agents/mkt/` (segmentation + consentement Loi 29-2019 + agent contenu) + overlay privé `ZolaCortex-Audit-Marketing` — [`docs/MARKETING_ROADMAP.md`](./docs/MARKETING_ROADMAP.md) |

Principe respecté partout : **déterministe d'abord, LLM pour interpréter/rédiger**. Forecasting prédictif et envoi réel = briques ultérieures (hors périmètre). Suite : **183 tests verts**.

---

*Addendum établi le 2026-06-20, extensions livrées le 2026-06-21. Complète V2.2 + V3 (Polaris).*
