#!/usr/bin/env python
"""Extrait le volet DÉFENSIF du bundle STIX MITRE ATT&CK Enterprise → texte RAG.

Source : `enterprise-attack.json` (bundle STIX 2.1, dépôt
github.com/mitre-attack/attack-stix-data). Parsé à la main (stdlib `json`
uniquement, pas de dépendance `stix2`) car on ne veut qu'un sous-ensemble
étroit du modèle.

Pour chaque `attack-pattern` (technique) actif — ni révoqué (`revoked`), ni
déprécié (`x_mitre_deprecated`) — on émet une section :
  - nom + identifiant ATT&CK (ex. T1078), lu dans `external_references` où
    `source_name == "mitre-attack"` ;
  - `description` ;
  - détection : deux schémas STIX coexistent selon la version du bundle.
    - historique : champ `x_mitre_detection` directement sur la technique ;
    - actuel (bundles générés depuis ATT&CK v17, fin 2025) : ce champ a
      disparu, remplacé par des relations `detects` reliant un objet
      `x-mitre-detection-strategy` à la technique, la stratégie référençant
      elle-même des `x-mitre-analytic` (le texte concret est dans leur
      `description`). On combine les deux, en préférant le champ historique
      s'il existe.
  - mitigations : relations `mitigates` dont la cible est la technique et la
    source un `course-of-action` → nom + description de chacune.

Volontairement DÉFENSIF : on ne garde ni les relations `uses` (mode
opératoire des groupes/malwares), ni les objets `intrusion-set`/`malware`/
`tool`/`campaign` — seulement description contextuelle + détection +
mitigation, pensés pour un défenseur, jamais des instructions d'attaque.

Usage :
    python scripts/extract_mitre_attack.py chemin/vers/enterprise-attack.json
    python scripts/extract_mitre_attack.py enterprise-attack.json --output data/cyber/mitre_attack_defensive.txt
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "cyber" / "mitre_attack_defensive.txt"

_SOURCE_MITRE = "mitre-attack"

_ENTETE = """MITRE ATT&CK Enterprise — volet défensif (détection & mitigations)
Source : enterprise-attack.json (bundle STIX 2.1), attributions MITRE
ATT&CK(R) — cf. Terms of Use (https://attack.mitre.org/resources/terms-of-use/).
{n} techniques actives (non révoquées, non dépréciées), triées par
identifiant ATT&CK. Volet strictement défensif : description contextuelle,
détection, mitigations — aucune procédure offensive.
"""


def _est_actif(obj: dict[str, Any]) -> bool:
    """Un objet STIX est actif s'il n'est ni révoqué ni marqué déprécié."""
    return not obj.get("revoked", False) and not obj.get("x_mitre_deprecated", False)


def _attack_id(obj: dict[str, Any]) -> str | None:
    """Identifiant ATT&CK (ex. T1078, T1055.011) d'un objet STIX, ou None."""
    for ref in obj.get("external_references", []) or []:
        if ref.get("source_name") == _SOURCE_MITRE and ref.get("external_id"):
            return str(ref["external_id"])
    return None


def _cle_tri(attack_id: str) -> tuple[int, int]:
    """Clé de tri numérique pour un identifiant ATT&CK (Txxxx[.yyy])."""
    m = re.match(r"^T(\d+)(?:\.(\d+))?$", attack_id)
    if not m:
        return (10**9, 0)
    return (int(m.group(1)), int(m.group(2)) if m.group(2) is not None else -1)


def _indexer(objets: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index STIX id → objet, pour résoudre les `*_ref` des relationships."""
    return {o["id"]: o for o in objets if "id" in o}


def _mitigations_par_technique(
    objets: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, list[tuple[str, str]]]:
    """Associe chaque technique (id STIX) à ses mitigations `(nom, description)`.

    Suit les relations `mitigates` : source = `course-of-action`,
    cible = `attack-pattern`. Trié par nom pour un rendu stable.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for rel in objets:
        if rel.get("type") != "relationship" or rel.get("relationship_type") != "mitigates":
            continue
        if not _est_actif(rel):
            continue
        coa = by_id.get(rel.get("source_ref", ""))
        if not coa or coa.get("type") != "course-of-action":
            continue
        cible = rel.get("target_ref", "")
        nom = (coa.get("name") or "").strip()
        desc = (coa.get("description") or "").strip()
        if nom:
            out.setdefault(cible, []).append((nom, desc))
    for liste in out.values():
        liste.sort(key=lambda t: t[0].lower())
    return out


def _detections_par_technique(
    objets: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> dict[str, str]:
    """Associe chaque technique (id STIX) à un texte de détection.

    Combine les deux schémas STIX (cf. docstring du module) : le champ
    historique `x_mitre_detection` s'il existe, sinon les stratégies de
    détection (`detects`) et leurs analytiques rattachées.
    """
    out: dict[str, str] = {}

    # Schéma historique : champ direct sur l'attack-pattern.
    for o in objets:
        if o.get("type") == "attack-pattern" and o.get("x_mitre_detection"):
            texte = str(o["x_mitre_detection"]).strip()
            if texte:
                out[o["id"]] = texte

    # Schéma actuel : detects (x-mitre-detection-strategy -> attack-pattern),
    # le contenu concret étant dans les x-mitre-analytic référencées.
    strategies_par_cible: dict[str, list[dict[str, Any]]] = {}
    for rel in objets:
        if rel.get("type") != "relationship" or rel.get("relationship_type") != "detects":
            continue
        if not _est_actif(rel):
            continue
        strategie = by_id.get(rel.get("source_ref", ""))
        if not strategie or strategie.get("type") != "x-mitre-detection-strategy":
            continue
        cible = rel.get("target_ref", "")
        strategies_par_cible.setdefault(cible, []).append(strategie)

    for cible, strategies in strategies_par_cible.items():
        if cible in out:
            continue  # champ historique déjà présent, priorité à celui-ci
        blocs: list[str] = []
        for strategie in strategies:
            analytiques: list[str] = []
            for ref in strategie.get("x_mitre_analytic_refs", []) or []:
                an = by_id.get(ref)
                if an and an.get("type") == "x-mitre-analytic":
                    desc = (an.get("description") or "").strip()
                    if desc:
                        analytiques.append(f"- {desc}")
            if analytiques:
                blocs.append("\n".join(analytiques))
        if blocs:
            out[cible] = "\n".join(blocs)

    return out


def _techniques_actives(objets: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    """Techniques (`attack-pattern`) actives, triées par identifiant ATT&CK."""
    techniques: list[tuple[str, dict[str, Any]]] = []
    for o in objets:
        if o.get("type") != "attack-pattern" or not _est_actif(o):
            continue
        aid = _attack_id(o)
        if aid:
            techniques.append((aid, o))
    techniques.sort(key=lambda t: _cle_tri(t[0]))
    return techniques


def construire_texte(objets: list[dict[str, Any]]) -> str:
    """Construit le texte RAG défensif à partir des objets d'un bundle STIX."""
    by_id = _indexer(objets)
    mitigations = _mitigations_par_technique(objets, by_id)
    detections = _detections_par_technique(objets, by_id)
    techniques = _techniques_actives(objets)

    lignes: list[str] = [_ENTETE.format(n=len(techniques))]
    for aid, tech in techniques:
        nom = (tech.get("name") or "").strip()
        desc = (tech.get("description") or "").strip()
        det = detections.get(tech["id"], "Non documentée dans les données STIX disponibles.")
        mits = mitigations.get(tech["id"], [])

        lignes.append("=" * 80)
        lignes.append(f"{aid} — {nom}")
        lignes.append("=" * 80)
        lignes.append("")
        lignes.append("Description")
        lignes.append("-" * 11)
        lignes.append(desc or "(non renseignée)")
        lignes.append("")
        lignes.append("Détection")
        lignes.append("-" * 9)
        lignes.append(det)
        lignes.append("")
        lignes.append("Mitigations")
        lignes.append("-" * 11)
        if mits:
            for nom_m, desc_m in mits:
                lignes.append(f"- {nom_m} : {desc_m}" if desc_m else f"- {nom_m}")
        else:
            lignes.append("(aucune mitigation associée dans les données STIX)")
        lignes.append("")

    return "\n".join(lignes) + "\n"


def charger_bundle(chemin: Path) -> list[dict[str, Any]]:
    """Charge un bundle STIX et retourne la liste `objects`."""
    data = json.loads(chemin.read_text(encoding="utf-8"))
    objets = data.get("objects")
    if not objets:
        raise ValueError(f"Bundle STIX vide ou invalide (clé 'objects' absente) : {chemin}")
    return objets


def main() -> int:
    p = argparse.ArgumentParser(
        description="Extrait le volet défensif de MITRE ATT&CK Enterprise (STIX) en texte RAG."
    )
    p.add_argument("stix_json", help="chemin du bundle STIX (enterprise-attack.json)")
    p.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"fichier texte à produire (défaut : {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = p.parse_args()

    objets = charger_bundle(Path(args.stix_json))
    texte = construire_texte(objets)
    nb_techniques = len(_techniques_actives(objets))

    sortie = Path(args.output)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(texte, encoding="utf-8")

    print(f"Bundle : {len(objets)} objets STIX.")
    print(f"Sortie : {sortie} ({len(texte):,} caractères, {nb_techniques} techniques).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
