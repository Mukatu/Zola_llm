# ZolaOS — Import/Export Excel : alimentation des données (sans ERP)

**Date** : 2026-06-25
**Statut** : roadmap **faisant autorité**. Troisième voie d'alimentation, à côté de la saisie manuelle et des connecteurs.
**Cadre** : persistance légère (système de référence) — pour les clients **sans ERP** (PME/administrations CG sur Excel/papier).

> Objectif : des **modèles Excel téléchargeables** (générés depuis le schéma) que l'entreprise remplit et **re-téléverse** ; validation **dry-run** ligne par ligne, puis import **idempotent**. Alimente les **mêmes tables `store_*`** que les écrans et les moteurs.

---

## 1. Les 3 voies d'alimentation
1. **Saisie manuelle** (formulaires) — ✅, lent pour du volume.
2. **Connecteurs ERP/API** (interop) — ✅ framework, suppose un ERP.
3. **Import Excel** — *cette roadmap* : la voie reine sans ERP.

## 2. Principes (non négociables)
- **Piloté par le schéma** : templates **générés** depuis les modèles canoniques → zéro dérive.
- **Déterministe d'abord** : toute la validation est **en code** ; LLM en option (mapping de colonnes mal nommées), jamais pour valider.
- **Sûr** : **dry-run** (rapport OK/erreurs + motifs) **avant** tout enregistrement ; import **partiel** (lignes valides) + journal des rejets.
- **Idempotent** : **upsert par clé naturelle** (ré-upload = mise à jour, pas de doublon).
- **Intégrité référentielle** : vérifier l'existence des références (matricule, code emploi/compétence…).
- **Multi-tenant**, portable (openpyxl, déjà en dépendance).

## 3. Framework (registre piloté par schéma)
Un **registre** déclare, par entité : `EntitySpec(entity, label, model, columns[Column], natural_key)`.
- `Column(name, kind[str|int|decimal|date|bool], required, enum, help)`.
- Source unique → **génère** le template, **valide** l'upload, **importe** (upsert).

## 4. Contenu d'un template (.xlsx)
- Feuille de données : **en-têtes exacts** (obligatoires marqués `*`), **listes déroulantes** pour les énumérations.
- Feuille **« Dictionnaire »** : colonne, type, obligatoire, valeurs permises, exemple/aide.
- (P2) Feuilles **de référence** : codes valides (matricules, codes emploi/compétence) pour cohérence.
- (P2) **Classeur par pôle** multi-feuilles (1 feuille/entité).

## 5. Endpoints
- `GET /v1/erp/import/entities` → catalogue (entités + colonnes).
- `GET /v1/erp/import/template/{entité}` → `.xlsx` généré.
- `POST /v1/erp/import/{entité}?dry_run=true` → **rapport** (total, valides, erreurs[ligne, motifs]).
- `POST /v1/erp/import/{entité}` → import (upsert) + journal (importés/mis à jour/rejetés).
- `GET /v1/erp/export/{entité}` → `.xlsx` des données existantes (relire/corriger/réimporter).

## 6. Clés naturelles (upsert)
Employés=`matricule` · Emplois=`code_emploi` · Compétences=`code_competence` · Matrice=`matricule+code_competence` · Factures=`numero` · Stock=`sku` · Vacances=`code_vacance` · Formations=`code`. Entités sans clé (contrats, absences, candidatures, sessions, inscriptions, évaluations) = **ajout**.

## 7. UI
**Écran transverse « Import / Export de données »** : choisir entité → Télécharger le modèle → Téléverser → **rapport de validation** → Confirmer.

## 8. Décisions validées (2026-06-25)
1. Classeur par pôle + templates par entité (le par-entité d'abord).
2. **Dry-run** obligatoire puis import **partiel** + rapport des rejets.
3. `.xlsx` principal (dropdowns + dictionnaire) ; CSV en option ultérieure.
4. **Écran transverse dédié**.

## 9. Découpage
- **IMP-1 (socle)** : framework (Column/EntitySpec, validate, build_template, parse, export) + endpoints + **2 pilotes : Employés + Factures** + tests + écran Import/Export.
- **IMP-2** : décliner à **toutes les entités** persistées (SIRH, supply, référentiels…) + feuilles de référence + classeur par pôle.
- **IMP-3** : assistance LLM au mapping de colonnes ; sync connecteurs → store.

## 10. Suivi
| Lot | Périmètre | Statut | Commit |
|-----|-----------|--------|--------|
| IMP-1 | Framework + Employés/Factures + écran | ✅ | `80caaf9` · `0c8e959` |
| IMP-2 | Toutes entités + références + classeur pôle | ☐ | — |
| IMP-3 | Assist LLM mapping + sync connecteurs | ☐ | — |

---

*Roadmap établie le 2026-06-25. Alimente les tables `store_*` ; déterministe, dry-run, idempotent.*
