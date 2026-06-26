# Échantillons

## `imports/` — modèles Excel du module Import

Classeurs `.xlsx` générés par le framework `zolaos.imports` (en-têtes, feuille
**Dictionnaire**, listes déroulantes, alias acceptés). Pratique pour montrer
concrètement ce qu'un utilisateur télécharge avant d'alimenter les tables `store_*`.

Les fichiers ne sont **pas versionnés** (openpyxl horodate chaque classeur →
diffs binaires). Pour les (re)générer :

```bash
python scripts/generate_import_samples.py samples/imports
```

Produit, dans `samples/imports/` :

- `modele_pole_<pole>.xlsx` — un classeur multi-feuilles par pôle
  (`rh`, `compta`, `commercial`, `achats`, `supply`).
- `modele_<entity>.xlsx` — un modèle par entité (17 entités).

Ils sont aussi téléchargeables depuis l'API quand le backend tourne :
`GET /v1/erp/import/template/pole/{pole}` et `GET /v1/erp/import/template/{entity}`.
