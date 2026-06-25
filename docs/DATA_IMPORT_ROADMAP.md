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
- `POST /v1/erp/import/{entité}` → import (upsert) + journal (importés/mis à jour/rejetés). `auto_map=true` (défaut) rapproche les en-têtes proches.
- `POST /v1/erp/import/{entité}/inspect` → **prévisualise** le mapping de colonnes (déterministe ; `use_llm=true` pour augmenter les en-têtes non résolus). N'écrit rien.
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
- **IMP-3** : **mapping de colonnes assisté** — rapprochement déterministe (accents/casse/ponctuation + alias déclarés + similarité) appliqué automatiquement à l'import (`auto_map`), endpoint `/inspect` de prévisualisation, augmentation LLM **optionnelle** (en-têtes non résolus uniquement, jamais pour valider).

> **Note de périmètre** : le bullet « sync connecteurs → store » initialement listé avec IMP-3 relève du **module interop/connecteurs**, pas du module Import Excel. Il est réassigné à la roadmap interop pour ne pas croiser deux modules. Le module **Import Excel est clos** avec IMP-3.

## 10. Suivi
| Lot | Périmètre | Statut | Commit |
|-----|-----------|--------|--------|
| IMP-1 | Framework + Employés/Factures + écran | ✅ | `80caaf9` · `0c8e959` |
| IMP-2 | Toutes entités (11) + **classeurs par pôle** (RH, Compta) multi-feuilles + écran à 2 modes | ✅ | `5fbabf0` |
| IMP-3 | **Mapping de colonnes assisté** (déterministe + LLM optionnel) + `/inspect` + écran | ✅ | _(ce lot)_ |
| — | _(réassigné interop)_ sync connecteurs → store | ➡️ | roadmap interop |

### Détail IMP-3 (livré 2026-06-25)
- **Moteur déterministe** `imports/mapping.py` : `normalize` (accents/casse/ponctuation), similarité (ratio de séquence ∪ Jaccard de jetons), **alias** déclarés par colonne, affectation gloutonne 1↔1, seuil 0.80.
- `Column.aliases` + alias renseignés sur Employés et Factures (pilotes) ; alias documentés dans la feuille **Dictionnaire** du template.
- **`auto_map=true`** par défaut sur `/import/{entité}` et `/import/pole/{pole}` : les en-têtes proches sont renommés avant validation ; le rapport expose `mapping{renommages, non_resolus}`.
- **`POST /import/{entité}/inspect`** : prévisualise le mapping (scores, champs manquants) sans rien écrire ; `use_llm=true` augmente les en-têtes non résolus via le client routeur 8B (dégradation gracieuse si LLM indisponible).
- **`imports/mapping_llm.py`** : suggestion LLM **optionnelle** (JSON mode, température 0), strictement complémentaire, jamais pour valider une donnée.
- Écran : bloc « colonnes reconnues / ignorées » dans le rapport (modes entité et pôle).

### Détail IMP-2 (livré 2026-06-25)
- **11 entités** câblées au registre : Employés, Contrats, Absences, Emplois (RME), Compétences (RMC), Profil requis, Matrice compétences, Vacances, Formations, Évaluations, Factures.
- **Classeurs par pôle** (`PoleSpec`) : `rh` (10 feuilles) et `compta` (1 feuille) — un onglet par entité + un **Dictionnaire global** (colonne « Entité »).
- Type de colonne **`list`** (valeurs séparées par `;`) pour activités/KPI/compétences visées.
- Endpoints pôle : `GET …/import/template/pole/{pole}`, `POST …/import/pole/{pole}` (rapport **par feuille**), `GET …/export/pole/{pole}`. `GET …/import/entities` expose désormais `poles`.
- **Écran à 2 modes** (Par pôle / Par type) : dry-run, rapport par feuille, confirmation, export.
- Prochaine déclinaison : pôles supply/commercial/finance à mesure que la persistance s'étend (clés naturelles déjà prévues §6).

---

*Roadmap établie le 2026-06-25. Alimente les tables `store_*` ; déterministe, dry-run, idempotent.*
