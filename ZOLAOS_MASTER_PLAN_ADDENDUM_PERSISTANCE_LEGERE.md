# ZolaOS — Addendum : positionnement produit & persistance légère

**Date** : 2026-06-23
**Statut** : addendum stratégique validé. Complète les plans/addenda existants ; ne remplace rien.
**Décision** : **hybride** — garder l'identité « couche IA souveraine », **interopérer fort** avec les ERP existants, **et** ajouter une **persistance légère** (système de référence scopé) pour les clients sans ERP.

---

## 1. Constat (Zolabox vs Odoo)

- **Odoo** = ERP **transactionnel** : *système de référence* qui **stocke et gère** les données métier (base + workflows + apps CRUD matures). Marché **mûr, commoditisé**.
- **Zolabox** = **couche cognitive IA** : orchestrateur multi-agents + moteurs **déterministes** + LLM, **souveraine et locale**, **multi-secteurs** (ERP **+ Santé, Droit, Code, Cyber, Pôle K**) + conseil augmenté **Polaris** (Zero Trust).
- Aujourd'hui, Zolabox **ne persiste pas** les enregistrements métier : elle **calcule / conseille / génère** et se **branche** aux systèmes via le **Connector Framework** (connecteur Odoo inclus).

## 2. Décision

**Ne pas devenir Odoo** (réimplémenter un ERP transactionnel complet diluerait le différenciateur IA et viserait un marché banalisé). À la place, deux leviers :

1. **Interopérer / augmenter** (le moat) : Zolabox = **cerveau IA *au-dessus*** du système de référence du client (Odoo / ERPNext / Sage / Excel) via les connecteurs.
2. **Persistance légère** : une **petite couche système-de-référence** pour les clients **sans ERP** (PME/cliniques/administrations sur Excel/papier), afin d'utiliser Zolabox **en standalone**.

## 3. Périmètre

**DANS** (persistance légère) — stockage CRUD des **entités déjà modélisées** par nos moteurs, multi-tenant + tags `country` + audit :
- Commercial : Customer, Opportunity, Quote
- Finance/Compta : Invoice, JournalEntry
- Supply/Achats : StockItem, Supplier
- RH : Employee
- Facility : Asset, Echeance · HSE : Incident, Risque · Sociétaire : Mandat · Marketing : MarketingContact

Les **moteurs déterministes** opèrent alors sur les **données stockées** (et plus seulement sur le corps de requête).

**HORS** (rester distinct d'Odoo → via interop) :
- Moteur de **workflow** complet, **MRP**, **POS**, **eCommerce**, **marketplace** d'apps, multi-société avancé, e-invoicing/archivage légal lourd, comptabilité auxiliaire exhaustive.

## 4. Architecture cible

- **Schéma PG dédié** (ex. `store`) + **ORM SQLAlchemy** + **repository pattern** + **migration Alembic**.
- **Multi-tenant** (`tenant_id`) + **RBAC** par tags ; **audit** des écritures (réutilise `audit.log`).
- **Endpoints CRUD** `/v1/erp/...` (profil box) ; les **connecteurs** alimentent aussi ces tables (sync depuis Odoo/Excel).
- **Réutilise les modèles canoniques** existants (zéro réinvention) ; chaque entité persistée = un modèle déjà présent.

## 5. Plan phasé

- **P1 — Socle** : schéma `store` + base repository + tenancy + **2-3 entités phares** (Factures, Stocks, Clients/Opportunités) en CRUD persistant ; brancher les moteurs (Supply/CRM/Finance) sur les données stockées.
- **P2 — Extension** : autres entités + **sync connecteurs** (import Odoo/CSV → store).
- **P3 — Front** : écrans CRUD (listes/formulaires) consommant la persistance ; le déterministe tourne sur les données réelles.

## 6. Garde-fous
- **Léger, scope maîtrisé** : on ne reconstruit pas Odoo. Si un besoin transactionnel lourd apparaît → **interop** plutôt que développement.
- Souveraineté/local-first et Zero Trust **inchangés**.

---

*Addendum établi le 2026-06-23. Identité = couche IA souveraine + interop ; ajout d'une persistance légère scopée.*
