"""Génère des échantillons .xlsx du module Import (modèles par pôle et par entité).

Permet d'inspecter concrètement les classeurs produits par le framework
(`zolaos.imports`) sans lancer l'API : en-têtes, feuille « Dictionnaire »,
listes déroulantes (enums) et alias acceptés.

Usage :
    python scripts/generate_import_samples.py [dossier_sortie]

Sortie (défaut `samples/imports/`) :
    modele_pole_<pole>.xlsx   — un classeur multi-feuilles par pôle
    modele_<entity>.xlsx      — un modèle par entité
"""

from __future__ import annotations

import sys
from pathlib import Path

from zolaos.imports.framework import build_pole_template, build_template
from zolaos.imports.registry import POLES, REGISTRY


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "samples/imports")
    out.mkdir(parents=True, exist_ok=True)

    for pole, spec in POLES.items():
        path = out / f"modele_pole_{pole}.xlsx"
        path.write_bytes(build_pole_template(spec))
        feuilles = ", ".join(e.label for e in spec.entities)
        print(f"[pole]   {path}  ({len(spec.entities)} feuilles : {feuilles})")

    for entity, spec in REGISTRY.items():
        path = out / f"modele_{entity}.xlsx"
        path.write_bytes(build_template(spec))
        print(f"[entity] {path}  ({len(spec.columns)} colonnes)")

    print(f"\n{len(POLES)} pôles + {len(REGISTRY)} entités générés dans {out.resolve()}")


if __name__ == "__main__":
    main()
