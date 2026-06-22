# ZolaOS — Addendum : Pilotage opérationnel (modules ERP étendus)

**Date** : 2026-06-22
**Statut** : addendum stratégique validé. Complète V2.2 + V3 (Polaris) + addendums BI/Commercial/Marketing + UX. Ne remplace rien.
**Décision** : ces 5 métiers deviennent des **modules de l'ERP** (pas de nouveau pôle — ERP « gros » unique). Côté client (**Zolabox**). Démarrage par **Supply Chain & Stocks**.

---

## 1. Objectif

Faire de la Zolabox le **hub de pilotage** d'une entreprise/administration d'Afrique centrale : accompagner la DG et les équipes opérationnelles, automatiser la conformité, valoriser les moteurs locaux 8B/70B. Cinq métiers opérationnels manquaient.

## 2. Principe (rappel)
**Déterministe d'abord** : le cœur (stocks, échéances, scoring, registres) est calculé **en code** ; le LLM **rédige** (BC, PV, contrats, rapports) et **interprète** ; RAG ciblé là où il y a du texte normatif. **Pas de forecasting LLM** : les « prédictions » au MVP sont des estimations **déterministes** (point de commande, jours avant rupture) ; la prévision ML reste une brique dédiée ultérieure.

## 3. Les 5 modules (tous `erp.*`, Zolabox / client)

| Module | Code | Cœur déterministe | Génératif | RAG ciblé |
|--------|------|-------------------|-----------|-----------|
| Supply Chain & Stocks | `erp.supply_chain` | point de commande, seuils, conso, jours avant rupture, alertes | bons de commande, bordereaux | — |
| Achats / Procurement | `erp.achats` | scoring fournisseurs, comparaison devis, contrôle conformité | contrats OHADA | offres reçues + OHADA commercial |
| Moyens Généraux / Facility | `erp.moyens_generaux` | calendrier maintenance préventive, échéances (assurances/visites/licences) | ordres de travail | contrats |
| Secrétariat sociétaire | `erp.secretariat_societaire` *(affinité GRC, placé ERP par décision)* | registre mandats/pouvoirs, échéancier légal | PV d'AG/CA, ordres du jour | AUSCGIE (OHADA sociétés) |
| HSE / RSE | `erp.hse` *(affinité GRC, placé ERP par décision)* | suivi incidents, registre risques, indicateurs RSE | plans de prévention, rapports durabilité | régl. environ. CG + standards bailleurs |

## 4. Données & synergies
- **Connector Framework** (déjà livré) : ces modules consommeront stocks/flotte/devis/incidents via connecteurs (modèles canoniques à ajouter au fil de l'eau : StockItem, Asset, PurchaseOrder, Supplier, Incident, ActeSociétaire).
- **Compta/CRM** : Achats ↔ factures fournisseurs ; Supply Chain ↔ commandes.
- **PII** : politiques d'ingestion au cas par cas (FISCAL/GENERIC).

## 5. Impact cabinet (Zolacortex) — Zero Trust
3 overlays d'audit (dépôt **privé**, mode mission, données client **anonymisées** via le pont éphémère) :
- `ZolaCortex-Audit-SupplyChain` (fraudes/vols, capitaux dormants),
- `ZolaCortex-Audit-Achats` (surfacturation, risques tiers),
- `ZolaCortex-Audit-HSE-Gouvernance` (responsabilité civile/pénale des dirigeants).
Rappel : **aucun accès direct** à la donnée client ; tout passe par la mission.

## 6. Séquence (build, déterministe d'abord)
1. **Supply Chain & Stocks** ← démarrage.
2. Achats / Procurement.
3. Moyens Généraux / Facility.
4. Secrétariat sociétaire.
5. HSE / RSE.
6. Overlays cabinet (3) + clôture.

## 7. Hors périmètre
- Forecasting prédictif ML (brique dédiée ultérieure).
- Envoi réel des bons de commande (via connecteurs plus tard).
- Écrans frontend (cadre d'écran de capacité — chantier UI).

---

## 8. Statut de réalisation (2026-06-22) — ✅ complet

| Module (Zolabox) | Code | État |
|------------------|------|------|
| Supply Chain & Stocks | `erp.supply_chain` | ✅ |
| Achats / Procurement | `erp.achats` | ✅ |
| Moyens Généraux / Facility | `erp.moyens_generaux` | ✅ |
| Secrétariat sociétaire | `erp.secretariat_societaire` | ✅ |
| HSE / RSE | `erp.hse` | ✅ |

Overlays cabinet (Zolacortex, dépôt privé, mode mission) : **ZolaCortex-Audit-SupplyChain**, **ZolaCortex-Audit-Achats**, **ZolaCortex-Audit-HSE-Gouvernance** ✅.

Tous déterministes d'abord (moteurs en code) + LLM pour rédaction/synthèse. Forecasting ML toujours hors périmètre. Suite : **220 tests verts**.

---

*Addendum établi le 2026-06-22, modules livrés le 2026-06-22. Modules ERP côté Zolabox ; overlays cabinet côté Zolacortex via mission (Zero Trust).*
