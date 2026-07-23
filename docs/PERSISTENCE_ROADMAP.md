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
| **P2b** | **Commercial / CRM** (Customer, Opportunity, Quote, Interaction) — back-end (P2b-1) + écran kanban persisté (P2b-2) | ✅ |
| **P2c** | **Achats** (Supplier, PurchaseOrder) + **SIRH-1** Core HR & pilotage (registres + tableau de bord + organigramme) → débloque **Paie** historisée | ⏳ |
| **P2c+** | **SIRH-2** Recrutement (pipeline + génération) · **SIRH-3** Développement/GPEC/Formation — voir `docs/SIRH_ROADMAP.md` | ⏳ |
| **P2d** | **Opérations** : Facility (Asset/Echeance), HSE (Risque/Incident), Marketing (MarketingContact/Campaign) | ⏳ |
| **P2e** | **Finance** (relevés bancaires persistés) + **Secrétariat** (Mandat) + **Projets ONG** (Projet/Budget) | ⏳ |
| **P2f** | **Documents** (transverse) : artefacts générés (contrats Droit, rapports, bulletins) → métiers génératifs | ⏳ |
| **P3** | BI branché sur le store (KPIs réels) ✅ · **trésorerie prévisionnelle** surfacée (moteur canonique) ✅ · multi-devise (MULTIDEV-1 socle gouverné ✅ · MULTIDEV-2 saisie en devise ✅) | ✅ |
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
**✅ MODULE CLOS (3 strates)** — `store_stock_items` + `store_stock_moves` :
- **Opérations** : grand-livre des mouvements (entrée/sortie/ajustement/transfert) **valorisé PMP** (SYSCOHADA classe 3) ; réappro/alertes rupture.
- **Gouvernance** : validation à **seuil + 2 niveaux** (N1/N2), **inventaire physique** (comptage→écart→ajustement), **lots & péremption** (alertes), **boucle Achats→Stock** (réception BC → entrée).
- **Pilotage** : valorisation totale, **taux de rotation**, **couverture en jours**, **taux de rupture**, **stock dormant**, **analyse ABC** + export Excel (`/stock/pilotage` & `/stock/pilotage/export`).
Import : pôle Supply à 2 feuilles (articles + mouvements).

**5. Achats / Procurement — ✅ MODULE CLOS (3 strates)**
Entités `store_suppliers` + `store_purchase_orders` + `store_engagements` + `store_purchase_budgets`. L'écran `AchatsScreen` a **3 onglets** :
- **Approvisionnement** : fournisseurs notés/gradés + conformité OHADA, BC, comparatif prix/délai, **réception → facture d'achat** (`sens="achat"` dans `store_invoices` ; clôture continue côté achat).
- **Engagements** (inspiré de l'outil métier réel) : chaîne **EB → DA → BC**, taux de transformation, funnel des statuts, délais de cycle, écart estimation/engagé, par direction/acheteur, alertes.
- **Pilotage CDG** : **engagé vs budget par direction** (consommation, niveaux ok/vigilance/dépassement), tendance mensuelle, concentration fournisseurs, sélecteur d'exercice.

Endpoints : `/v1/erp/{suppliers,purchase-orders,engagements,purchase-budgets}` (CRUD) + `suppliers/scores`, `purchase-orders/compare`, `purchase-orders/{id}/receipt`, `engagements/stats`, `engagements/pilotage?exercice=` et **`engagements/pilotage/export`** (classeur CDG calculé : synthèse + engagé/budget par direction + mensuel + fournisseurs). Import : pôle Achats à **4 feuilles** (alias alignés sur le fichier métier réel).
**Plus-value** : registre fournisseurs, anti-surfacturation tracée, encours fournisseurs réel, **suivi des engagements et pilotage budgétaire** (contrôle de gestion).

**6. RH — SIRH complet (3 piliers) — ⏳ (P2c → SIRH-1/2/3)** · **plan détaillé : `docs/SIRH_ROADMAP.md`**
Objectif : un **SIRH de pilotage** couvrant **Recrutement**, **Administration du Personnel**, **Développement du Capital Humain (GPEC/Formation)** — registres persistés + **indicateurs déterministes** + **génération d'artefacts** (fiches de poste, contrats CDI/CDD en masse, grilles d'entretien, plans de formation, plan GPEC, matrice risques/opportunités, organigramme…) + échéanciers/alertes. LLM rédige (brouillons validés), l'humain valide ; le lourd (LMS, job boards, pointage, BPM) → interop.
Sous-phases : **SIRH-1** Core HR & pilotage (= ce bloc P2c) · **SIRH-2** Recrutement · **SIRH-3** Développement/GPEC. *Détail entités/endpoints/écrans/indicateurs : voir `docs/SIRH_ROADMAP.md`.*

*Entités persistées* (canonique : `connectors.models.Employee`, étendu) :
- `store_employees` (riche) : matricule, nom, genre, date_naissance, date_embauche, poste, département, manager_id, catégorie/échelon, salaire_base_xaf, statut (actif/sorti), date_sortie, motif_sortie, lieu.
- `store_contracts` : type (CDI/CDD/stage/prestation), date_début, date_fin, fin_période_essai, statut.
- `store_absences` : type (congé payé/maladie/maternité/sans solde), date_début, date_fin, jours, statut.
- `store_hr_movements` (ou dérivé) : embauche/départ/mutation/promotion + date.

*Moteur déterministe* (`agents/erp/rh_pilotage.py`) — **indicateurs RH calculés en code** :
effectif total + **ETP**, répartition par département/contrat/genre ; **masse salariale** (totale, moyenne/médiane) ; **turnover** (taux de rotation) ; **ancienneté moyenne** + pyramide ; **pyramide des âges** ; **taux d'absentéisme** ; **ratio d'encadrement** ; **index égalité H/F** (répartition + écart salarial). Tous exacts, sans LLM.

*Endpoints* : CRUD `/v1/erp/employees`, `/contracts`, `/absences` ; `/v1/erp/hr/dashboard` (indicateurs sur le store — **le pilotage**) ; `/v1/erp/hr/echeancier` (fins de période d'essai, fins de CDD, visites médicales, anniversaires d'ancienneté, congés à solder) ; `/v1/erp/hr/registre` (**registre unique du personnel** — export légal OHADA/CG).

*Écran* `RHScreen` (🆕 riche, 3 onglets) : **Registre** (liste + fiche employé + ajout) · **Tableau de bord** (KPIs + mini‑graphes : effectif, masse salariale, turnover, absentéisme, égalité H/F, ancienneté) · **Échéancier RH**. + synthèse rédigée par l'agent RH (LLM).

*Conformité* : registre unique du personnel (obligation légale), suivi des échéances sociales/CNSS.

**Plus-value** : un **SIRH qui aide à piloter** (et pas un simple annuaire) — registre légal + tableau de bord RH + échéancier proactif, déterministe + narration IA. Prérequis de la Paie historisée.

**Hors périmètre (→ interop / phase ultérieure)** : ATS recrutement, LMS/formation, entretiens & performance (workflow), pointage temps réel, portail self‑service avec circuits de validation. *(On reste « pilotage + registres », pas une suite RH transactionnelle.)*

**7. Paie — ⏳ (P2c+, dépend du SIRH)**
Entité `store_payslips`. Endpoint `/v1/erp/payslips` (génère depuis l'employé **stocké** + barème, persiste). Écran `PaieScreen` (🔁 : sélection employé du registre → bulletin → historique).
**Plus-value** : historique des bulletins, **masse salariale réelle** qui alimente le tableau de bord RH **et** la BI.

**8. Projets ONG — ✅ (P2e)**
Entités `store_projects` + `store_budget_lines` (ventilation bailleur/projet). Endpoints `/v1/erp/projects` + `/budget-lines` (CRUD) + `/projects/{id}/suivi` (taux d'exécution/engagement par rubrique, dépassement, éligible vs total) + `/projects/ventilation` (agrégat par bailleur). Écran `ProjetsOngScreen` (registre projets + lignes budgétaires + suivi + ventilation). Tests `test_store_projets.py`.
**Plus-value** : suivi budgétaire bailleurs, reporting (lien GRC reporting).

**9. Secrétariat sociétaire — ✅ (P2e)**
Entités `store_mandates` + `store_resolutions` (AG/PV). Endpoints `/v1/erp/mandates` + `/resolutions` (CRUD) + `/corporate/echeances` (moteur légal sur le store : mandats à renouveler + date limite AGO AUSCGIE). Écran `SecretariatScreen`. Tests `test_store_secretariat.py`.
**Plus-value** : registre des mandats, calendrier statutaire/légal.

### B. Pôles Commercial / Marketing / BI

**10. Commercial / CRM — ✅ (P2b : back-end P2b-1, écran kanban persisté P2b-2)**
Entités `store_customers` + `store_opportunities` + `store_quotes` + `store_interactions` (canoniques : `crm.models`). Endpoints `/v1/crm/customers|opportunities|quotes|interactions` (CRUD) + `PATCH /opportunities/{id}/stage` (kanban) + `GET /crm/analyze` (🔁 : pipeline/scoring/relances sur données **stockées**, score affiné par source client et dernière interaction) + `GET /crm/forecast` (prévision pondérée par mois de clôture) + `POST /quotes/{id}/convert` (matérialise une **facture** dans `store_invoices` → branche la clôture continue). Écran `CrmScreen` (P2b-2 : kanban sur **vrai pipeline** + drag-stage persisté + relances + mini-forecast + timeline d'interactions).
**Plus-value** : pipeline réel suivi dans le temps, conversion mesurée jusqu'à la facture, relances proactives sur l'encours.

**11. Marketing — ⏳ (P2d)**
Entités `store_marketing_contacts` (canonique : `mkt.models.MarketingContact`) + `store_campaigns`. Endpoints `/v1/mkt/contacts` (CRUD) + `/mkt/audience` (🔁 sur contacts stockés) + `/campaigns`. Écran `MarketingScreen` (🔁 : base contacts + journal de consentement persistant).
**Plus-value** : base d'audience réelle, **traçabilité du consentement** (Loi 29-2019) dans le temps.

**12. BI / Pilotage — ✅ (P3, cockpit + trésorerie prévisionnelle)**
Pas d'entité propre. Cockpit agrégé sur le **store** : `/v1/bi/{dashboard,cockpit}` (KPIs réels cross-métiers + signaux + échéances), `/brief` et `/ask` (LLM narre). `BiScreen` consomme ces flux réels.
**Prévision de trésorerie** surfacée dans le cockpit via le **moteur canonique** `/v1/erp/treasury/pilotage` (`previsionnel_tresorerie` — *zéro réinvention*) : trajectoire du solde projeté 90 j (sparkline SVG), alerte de découvert daté, DSO/DPO/BFR/runway. Écran `PilotageCard` dans `BiScreen`.
**Plus-value** : pilotage sur chiffres réels et continus (CA, marge, DSO, trésorerie) **+ vue prospective** (découvert anticipé, runway).
**Reste P3** : multi-devise (table de taux + conversion à l'affichage) ; enrichissements cockpit (masse salariale sur paie réelle, exécution budgétaire projets ONG, échéances mandats).

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
- **Multi-devise** (P3) : **MULTIDEV-1 ✅** — table de taux **gouvernée** `store_fx_rates` (graine `ref/fx_rates_cg.json` : EUR 655,957 validé/parité BEAC, XOF 1:1 ; USD/GBP/CNY non validés = à saisir), moteur `agents/erp/fx.py` (`convertir`, abstention si non validé), endpoints `/v1/erp/fx/*`, écran `erp.devises` (panneau gouverné + convertisseur). XAF reste la référence canonique. **MULTIDEV-2 ✅** : saisie de factures en devise → normalisation XAF **à l'écriture** au taux validé (409 sinon) ; colonnes `montant_ht_devise`/`montant_ttc_devise`/`taux_applique` sur `store_invoices` pour la traçabilité (migration 0051) ; les `_xaf` restent canoniques donc **BI/trésorerie inchangés** (une facture EUR contribue en XAF normalisé). Front : sélecteur de devise + aperçu XAF au taux dans le registre.
- **Prévision de trésorerie** (P3) : ✅ **déterministe** (pas ML, pas LLM) — `previsionnel_tresorerie` (moteur canonique `agents/erp/treasury.py`, exposé `/v1/erp/treasury/pilotage`) surfacée dans le cockpit BI. Une brique ML resterait optionnelle (au-delà du déterministe) si un besoin de saisonnalité émergeait.
- **Sync connecteurs → store** : import Odoo/CSV alimente les tables `store_*` (interop + standalone).
- **Audit** : journaliser les écritures sensibles (réutilise `audit`).

## 6. Ordre d'exécution recommandé (et pourquoi)
1. **P2b Commercial** — écran le plus parlant après la compta ; prouve la généralisation. *(priorité)*
2. **P2c Achats + SIRH de pilotage (+ Paie)** — registres structurants + **tableau de bord RH** ; débloque la Paie historisée. *(RH = bloc enrichi : à livrer en 2 temps — registres/contrats puis absences/dashboard/échéancier.)*
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
| P2b | Commercial | ✅ | back-end P2b-1 (registres + endpoints + moteur sur store + tests) + front P2b-2 (kanban persisté, drag-stage, score, relances, forecast, timeline, devis→facture) |
| P2c | Achats, SIRH (RH pilotage), Paie | 🔄 | Achats ✅ (P2c-1 back-end + P2c-2 écran : registre noté, conformité, comparatif, réception→facture). SIRH livré séparément ; Paie historisée reste à faire |
| P2d | Facility, HSE, Marketing | ✅ | back-end + écrans livrés (le doc était en retard) |
| P2e | Finance, Secrétariat, Projets ONG | ✅ | Finance ✅, **Projets ONG ✅**, **Secrétariat/Mandat ✅** (2026-07-22) |
| P2f | Documents (Droit/Santé/Code) | ✅ | ORM/repo/routes ✅, écran (page `/documents` : liste + suppression) ✅, nav Sidebar ✅ ; tests dédiés ajoutés (2026-07-22) |
| P3 | BI store, prévision trésorerie, multi-devise | 🔄 | BI cockpit sur store ✅ ; trésorerie prévisionnelle surfacée (moteur canonique, zéro réinvention) ✅ ; multi-devise MULTIDEV-1 (taux gouvernés + conversion + écran) ✅, MULTIDEV-2 (factures en devise → normalisation XAF, traçabilité) ✅ → **P3 clos** |
| PX | Fintech, GRC, Cyber, Pôle K | ☐ | — |

---

*Plan établi le 2026-06-23. À suivre métier par métier selon le patron §2. Mettre à jour le tableau de suivi §7 et `docs/ETAT_PROJET.md` §3bis à chaque livraison.*
