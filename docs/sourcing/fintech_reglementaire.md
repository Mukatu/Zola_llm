# Sourcing — corpus réglementaire fintech (`rag_fintech`)

Catalogue des **sources réglementaires réelles** à ingérer dans le corpus
`rag_fintech` (pôle fintech : microfinance, LBC-FT, systèmes de paiement, zone
CEMAC / République du Congo).

> **Règle de non-fabrication.** Ce corpus ne doit contenir que des **textes
> officiels obtenus des sources ci-dessous**. Aucun seuil, taux ou ratio
> réglementaire n'est saisi de mémoire. Tant que les textes ne sont pas
> récupérés, seule une **fiche d'orientation** (institutions et périmètres,
> sans valeur chiffrée, `validated:false`) est ingérée.

## Institutions et périmètres

| Institution | Rôle | Périmètre pour le pôle |
|---|---|---|
| **COBAC** — Commission Bancaire de l'Afrique Centrale | Supervision des établissements de crédit et de **microfinance (EMF)** en zone CEMAC | Conditions d'exercice, agrément, ratios prudentiels des EMF |
| **GABAC** — Groupe d'Action contre le Blanchiment d'Argent en Afrique Centrale | Organisme régional type GAFI (LBC-FT) | Obligations de vigilance (KYC), déclaration de soupçon, gel |
| **BEAC** — Banque des États de l'Afrique Centrale | Émission monétaire, **systèmes et services de paiement** | Mobile Money / monnaie électronique, prestataires de paiement |
| **CEMAC / UMAC** | Édiction des règlements communautaires | Cadre LBC-FT, microfinance, paiements |
| **République du Congo** | Droit national applicable | Loi 29-2019 (protection des données), fiscalité EMF |

## Textes de référence à récupérer (portails officiels)

- **Microfinance / EMF** : règlement CEMAC/UMAC/COBAC relatif à l'exercice et au
  contrôle de l'activité de microfinance (famille des règlements EMF).
- **LBC-FT** : règlement CEMAC/UMAC/CM portant prévention et répression du
  blanchiment des capitaux et du financement du terrorisme.
- **Systèmes de paiement** : règlement CEMAC relatif aux services de paiement
  (monnaie électronique, Mobile Money).
- **Données personnelles** : Loi n° 29-2019 (République du Congo).

Portails : BEAC (beac.int), COBAC, Secrétariat CEMAC, GABAC, Journal Officiel CG.

## Convention d'ingestion

- Schéma : `rag_fintech`. Tags : `country:cg`, `country:cemac`, `module:<domaine>`
  (`microfinance`, `lbcft`, `paiements`, `data`), `source:<institution>`, et
  `validated:true|false`.
- Chaque texte porte `source_uri` = URL officielle ; `source_id` = référence du
  texte. Métadonnée `validated:true` **uniquement** pour un texte officiel vérifié.
- Ingestion : `python scripts/ingest_fintech.py` (traite `data/fintech/`).
