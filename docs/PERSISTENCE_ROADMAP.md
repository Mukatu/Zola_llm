# ZolaOS — Plan d'action : généralisation de la persistance (système de référence léger)

**Date** : 2026-06-23
**Statut** : feuille de route **faisant autorité** à suivre scrupuleusement, métier par métier, jusqu'au bout.
**Cadre** : addendum `ZOLAOS_MASTER_PLAN_ADDENDUM_PERSISTANCE_LEGERE.md` (hybride vs Odoo : couche IA + interop + persistance légère) · inventaire `docs/ETAT_PROJET.md` §3bis.

> Objectif : faire passer **chaque métier** de « calcule à la demande » (sans mémoire) à « tient un **registre vivant** » (persisté), que l'IA réconcilie et pilote en continu — sans devenir Odoo (scope maîtrisé).

---

## 1. Principes (non négociables)
1. **Déterministe d'abord** : les chiffres/règles en code ; le LLM interprète/rédige.
2. **Zéro réinvention** : chaque entité persistée réutilise un **modèle canonique déjà existant** (connectors/agents).
3. **Socle commun** : `StoreBase` (metadata dédiée) + **repository pattern** + migrations Alembic + tests **SQLite** (override `get_session`).
4. **Multi-tenant** (`tenant_id`), horodaté, portable **PostgreSQL/SQLite**.
5. **Scope léger** : besoin transactionnel lourd (workflow/MRP/POS/e-invoicing) → **interop**, pas développement.
6. **Qualité** : black + ruff + mypy verts (versions épinglées) ; suite de tests verte ; étanchéité dépôts à chaque commit.

## 2. Patron de livraison (recette répétable, identique pour chaque métier)
Pour chaque métier, **7 livrables** :
1. **ORM** : `XxxRecord(StoreBase)` dans `src/zolaos/db/store_models.py` (table `store_xxx`, `to_dict()`).
2. **Repository** : `XxxRepository` dans `src/zolaos/db/store_repo.py` (create/get/list/update/delete, filtré tenant).
3. **Endpoints** : CRUD `/v1/erp/...` (ou pôle dédié) + **moteur branché sur le store** (l'analyse tourne sur les données stockées).
4. **Migration** Alembic (`store_xxx`, schéma par défaut, portable).
5. **Tests** : `tests/test_store_<metier>.py` (CRUD SQLite + moteur sur store).
6. **Front** : client typé (`lib/store.ts`/dédié) + écran (nouveau ou évolution) consommant le store.
7. **Intégration** : nav/catalogue si nouvelle capacité ; doc/CHANGELOG mis à jour.

**Definition of Done (par métier)** : 7 livrables faits · tests verts · black/ruff/mypy verts · typecheck/lint/build front verts · commit public propre (anti-fuite) + privé si overlay touché.

## 3. Phasage global

| Phase | Métiers | Statut |
|-------|---------|--------|
| P1 | Facturation/Registre (Factures) + **clôture continue** | ✅ |
| P1b | Écran « Registre & clôture vivante » | ✅ |
| P2 | Comptabilité (Écritures + **balance vivante**) + Supply (Stocks) + **auto-catégorisation** | ✅ |
| **P2b** | **Commercial / CRM** (Customer, Opportunity, Quote) | ⏳ à faire |
| **P2c** | **Achats** (Supplier, PurchaseOrder) + **RH** (Employee, Contract) → débloque **Paie** historisée | ⏳ |
| **P2d** | **Opérations** : Facility (Asset/Echeance), HSE (Risque/Incident), Marketing (MarketingContact/Campaign) | ⏳ |
| **P2e** | **Finance** (relevés bancaires persistés) + **Secrétariat** (Mandat) + **Projets ONG** (Projet/Budget) | ⏳ |
| **P2f** | **Documents** (transverse) : artefacts générés (contrats Droit, rapports, bulletins) → métiers génératifs | ⏳ |
| **P3** | BI branché sur le store (KPIs réels) · **prévision de trésorerie** (ML) · multi-devise | ⏳ |
| **PX** | Pôles à construire : **Fintech** (scoring/KYC), **GRC complet**, **Cyber**, **Pôle K** | ⏳ |

---

## 4. Plan détaillé — métier par métier

> Légende : ✅ fait · ⏳ à faire · 🔁 évolution d'un écran existant · 🆕 nouvel écran.

### A. Pôle ERP / Finance

**1. Facturation / Registre — ✅ (P1/P1b)**
Entité `store_invoices` (canonique : `connectors.models.Invoice`). Endpoints `/v1/erp/invoices` (CRUD) + `/reconcile`. Écran `RegistreScreen` (🆕). Moteur : `reconciliation.reconcilier` (clôture continue).
*Reste* : avoirs, échéancier clients. **Plus-value** : encours, clôture continue.

**2. Comptabilité — Écritures — ✅ (P2)**
`store_journal_entries` (canonique : `JournalEntry`/`JournalLine`). Endpoints `/v1/erp/journal` (CRUD), `/journal/balance` (**balance vivante**). Écran `ComptaScreen` (🔁 : saisie→valider→enregistrer→balance) + **auto-catégorisation** (`/compta/suggest`).
*Reste* : lettrage analytique, journaux multiples, exercices. **Plus-value** : grand livre + balance toujours à jour.

**3. Finance / Trésorerie — ⏳ (P2e)**
Entité **nouvelle** `store_bank_transactions` (canonique : `connectors.models.BankTransaction`). Endpoints `/v1/erp/treasury/transactions` (CRUD) + `/treasury/cashflow` (solde glissant). Écran `FinanceScreen` (🔁 : anomalies sur transactions **stockées** + position de trésorerie).
**Plus-value** : trésorerie réelle, anomalies en continu, base de la prévision (P3).

**4. Supply Chain / Stocks — ✅ (P2)**
`store_stock_items` (canonique : `supply.StockItem`). Endpoints `/v1/erp/stock` (CRUD) + `/stock/analyze`. Écran `SupplyScreen` (🔁 : stock persistant + analyse).
*Reste* : `store_stock_moves` (entrées/sorties), lots/péremption, valorisation. **Plus-value** : stock réel, réappro auto.

**5. Achats / Procurement — ⏳ (P2c)**
Entités `store_suppliers` (canonique : `achats.Supplier`) + `store_purchase_orders` (lignes JSON ; devis comparés → BC). Endpoints `/v1/erp/suppliers` (CRUD + score/conformité) + `/purchase-orders` (CRUD + comparatif). Écran `AchatsScreen` (🔁 : registre fournisseurs + historique devis/BC).
**Plus-value** : registre fournisseurs, historique d'achats, anti-surfacturation tracée.

**6. RH — ⏳ (P2c)**
Entités `store_employees` (canonique : `connectors.models.Employee`) + `store_contracts`. Endpoints `/v1/erp/employees` (CRUD) + `/contracts`. Écran RH (🔁 de générique → 🆕 registre du personnel).
**Plus-value** : registre des employés/contrats — **prérequis de la Paie historisée**.

**7. Paie — ⏳ (P2c+, dépend de RH)**
Entité `store_payslips`. Endpoint `/v1/erp/payslips` (génère depuis `Employee` + barème, persiste). Écran `PaieScreen` (🔁 : sélection employé stocké → bulletin → historique).
**Plus-value** : historique des bulletins, masse salariale réelle (alimente BI).

**8. Projets ONG — ⏳ (P2e)**
Entités `store_projects` + `store_budget_lines` (ventilation bailleur/projet). Endpoints `/v1/erp/projects` (CRUD + suivi budget). Écran Projets (🆕).
**Plus-value** : suivi budgétaire bailleurs, reporting (lien GRC reporting).

**9. Secrétariat sociétaire — ⏳ (P2e)**
Entités `store_mandates` + `store_resolutions` (AG/PV). Endpoints `/v1/erp/corporate` (CRUD + échéances légales). Écran Secrétariat (🆕).
**Plus-value** : registre des mandats, calendrier statutaire/légal.

### B. Pôles Commercial / Marketing / BI

**10. Commercial / CRM — ⏳ (P2b, PRIORITÉ)**
Entités `store_customers` + `store_opportunities` + `store_quotes` (canoniques : `crm.models`). Endpoints `/v1/crm/customers|opportunities|quotes` (CRUD) + `/crm/analyze` (🔁 : pipeline/scoring/relances sur données **stockées**). Écran `CrmScreen` (🔁 : kanban sur **vrai pipeline** + drag-stage persisté + relances).
**Plus-value** : pipeline réel suivi dans le temps, conversion mesurée, relances proactives sur l'encours.

**11. Marketing — ⏳ (P2d)**
Entités `store_marketing_contacts` (canonique : `mkt.models.MarketingContact`) + `store_campaigns`. Endpoints `/v1/mkt/contacts` (CRUD) + `/mkt/audience` (🔁 sur contacts stockés) + `/campaigns`. Écran `MarketingScreen` (🔁 : base contacts + journal de consentement persistant).
**Plus-value** : base d'audience réelle, **traçabilité du consentement** (Loi 29-2019) dans le temps.

**12. BI / Pilotage — ⏳ (P3)**
Pas d'entité propre. Endpoint `/v1/bi/kpis` (🔁 : agrège le **store** au lieu du corps de requête). Écran `BiScreen` (🔁 : KPIs sur données réelles).
**Plus-value** : pilotage sur chiffres réels et continus (CA, marge, DSO, trésorerie, masse salariale).

### C. Pôle Opérations (Facility / HSE)

**13. Moyens Généraux / Facility — ⏳ (P2d)**
Entités `store_assets` + `store_echeances` (canoniques : `facility.Asset`/`Echeance`). Endpoints `/v1/erp/facility/assets|echeances` (CRUD) + `/facility/echeancier` (🔁 sur stock). Écran `FacilityScreen` (🔁 : registre des actifs + échéancier maintenance/assurances).
**Plus-value** : registre des actifs, maintenance préventive planifiée, alertes d'échéances.

**14. HSE / RSE — ⏳ (P2d)**
Entités `store_risks` + `store_incidents` (canonique : `hse.Risque`). Endpoints `/v1/erp/hse/risks|incidents` (CRUD) + `/hse/cartographie` (🔁 sur stock). Écran `HseScreen` (🔁 : registre des risques suivi + journal d'incidents).
**Plus-value** : registre des risques vivant, criticité suivie, conformité HSE traçable.

### D. Métiers génératifs (persistance = artefacts, pas registre transactionnel)

**15. Droit / Santé / Code — ⏳ (P2f via Documents)**
Pas de registre métier ; on persiste les **artefacts générés** (contrats, fiches, snippets) dans une entité transverse `store_documents` (type, métier, contenu, tags, tenant). Endpoints `/v1/documents` (CRUD + recherche). Écran **Documents** (🔁 : la page existante liste les documents réels).
**Plus-value** : mémoire des livrables (contrats signés, fiches, rapports), réutilisation, audit.

### E. Pôles à construire (moteur + écran + persistance — hors « léger », vrai chantier)

**16-17. Fintech — Scoring crédit & KYC/AML — ⏳ (PX)**
Construire d'abord les **moteurs** (scoring déterministe ; KYC : complétude + screening sanctions filtré), puis persistance `store_credit_applications` + `store_kyc_files`, endpoints `/v1/fintech/*`, écrans dédiés. Connecteurs MoMo/Airtel (sandbox) en option.
**Plus-value** : dossiers de crédit et KYC tracés (conformité ANIF/COBAC).

**18. GRC complet — ⏳ (PX)**
Compléter les moteurs (conformité, audit institutionnel, reporting bailleurs), persistance `store_obligations` + `store_controls` + `store_findings`, endpoints `/v1/grc/*`, écrans.
**Plus-value** : registres d'obligations/contrôles/constats, plans d'action suivis.

**19. Cyber-défense — ⏳ (PX)** · **Pôle K (langues) — ⏳**
Cyber : moteur + écran (hors persistance lourde initiale). Pôle K : dictionnaires Lingala/Kituba (i18n front déjà prêt).

---

## 5. Transverses (jalons techniques)
- **`store_documents`** (P2f) : socle des artefacts génératifs (réutilisé par Droit/Santé/Code/rapports).
- **Multi-devise** (P3) : champ `devise` déjà présent ; ajouter table de taux + conversion à l'affichage.
- **Prévision de trésorerie** (P3) : **brique ML dédiée** (pas LLM), sur `store_bank_transactions` + factures.
- **Sync connecteurs → store** : import Odoo/CSV alimente les tables `store_*` (interop + standalone).
- **Audit** : journaliser les écritures sensibles (réutilise `audit`).

## 6. Ordre d'exécution recommandé (et pourquoi)
1. **P2b Commercial** — écran le plus parlant après la compta ; prouve la généralisation. *(priorité)*
2. **P2c Achats + RH (+ Paie)** — registres structurants ; débloque la Paie historisée.
3. **P2d Facility + HSE + Marketing** — registres « opérations » à fort effet visuel (échéanciers, risques, consentement).
4. **P2e Finance (banque) + Secrétariat + Projets ONG** — complète le back-office ; alimente la trésorerie.
5. **P2f Documents** — mémoire des livrables génératifs.
6. **P3** — BI sur store + prévision ML + multi-devise.
7. **PX** — Fintech, GRC complet, Cyber, Pôle K (vrais nouveaux pôles).

À chaque phase : 1 commit par métier (patron §2), suite verte, doc mise à jour (ETAT_PROJET §3bis + ce fichier).

## 7. Suivi
| Phase | Métier | DoD | Commit |
|-------|--------|-----|--------|
| P1/P1b/P2 | Factures, Écritures, Stocks | ✅ | `de476ea`,`22eccbd`,`16d3c1b`,`8edc431`,`6612f3a` |
| P2b | Commercial | ☐ | — |
| P2c | Achats, RH, Paie | ☐ | — |
| P2d | Facility, HSE, Marketing | ☐ | — |
| P2e | Finance, Secrétariat, Projets ONG | ☐ | — |
| P2f | Documents (Droit/Santé/Code) | ☐ | — |
| P3 | BI store, prévision ML, multi-devise | ☐ | — |
| PX | Fintech, GRC, Cyber, Pôle K | ☐ | — |

---

*Plan établi le 2026-06-23. À suivre métier par métier selon le patron §2. Mettre à jour le tableau de suivi §7 et `docs/ETAT_PROJET.md` §3bis à chaque livraison.*
