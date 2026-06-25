"""Mapping de colonnes assisté (IMP-3) — rapprochement déterministe d'en-têtes.

Quand un fichier téléversé n'a pas exactement les en-têtes attendus (casse,
accents, ponctuation, synonymes…), on **propose** un mapping en-tête → champ
par similarité : normalisation + alias déclarés + ratio de séquence. Affectation
gloutonne (un en-tête ↔ un champ). Entièrement **déterministe** ; une
augmentation LLM optionnelle (voir `mapping_llm`) traite les en-têtes non résolus.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from zolaos.imports.framework import EntitySpec

# Seuil de confiance par défaut : en deçà, on laisse l'en-tête « non résolu »
# (pas de mapping hasardeux qui ferait passer une mauvaise colonne).
SEUIL_DEFAUT = 0.80


def normalize(value: str) -> str:
    """Minuscule, sans accents, ponctuation → espaces, espaces compactés."""
    txt = unicodedata.normalize("NFKD", str(value))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = "".join(c if c.isalnum() else " " for c in txt.lower())
    return " ".join(txt.split())


def _similarite(a: str, b: str) -> float:
    """Combine ratio de séquence et recouvrement de jetons (max des deux)."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return max(ratio, jaccard)


def _meilleur_score(header: str, spec_col_name: str, aliases: tuple[str, ...]) -> float:
    """Meilleure similarité entre un en-tête et (nom de champ + ses alias)."""
    return max(_similarite(header, cand) for cand in (spec_col_name, *aliases))


@dataclass(frozen=True)
class MappingResult:
    """Proposition de mapping pour un fichier donné."""

    mapping: dict[str, str]  # en-tête fichier -> nom de champ
    scores: dict[str, float]  # nom de champ -> score de confiance
    non_resolus: list[str]  # en-têtes sans champ retenu
    champs_couverts: list[str]
    champs_manquants: list[str]  # champs obligatoires non couverts


def propose_mapping(
    spec: EntitySpec, headers: list[str], *, seuil: float = SEUIL_DEFAUT
) -> MappingResult:
    """Propose un mapping en-tête → champ (affectation gloutonne, 1↔1)."""
    # Toutes les paires (en-tête, champ, score) au-dessus du seuil.
    paires: list[tuple[float, str, str]] = []
    for header in headers:
        for col in spec.columns:
            score = _meilleur_score(header, col.name, col.aliases)
            if score >= seuil:
                paires.append((score, header, col.name))
    paires.sort(key=lambda p: -p[0])

    mapping: dict[str, str] = {}
    scores: dict[str, float] = {}
    headers_pris: set[str] = set()
    champs_pris: set[str] = set()
    for score, header, champ in paires:
        if header in headers_pris or champ in champs_pris:
            continue
        mapping[header] = champ
        scores[champ] = round(score, 3)
        headers_pris.add(header)
        champs_pris.add(champ)

    non_resolus = [h for h in headers if h not in headers_pris]
    champs_couverts = list(champs_pris)
    champs_manquants = [c.name for c in spec.columns if c.required and c.name not in champs_pris]
    return MappingResult(mapping, scores, non_resolus, champs_couverts, champs_manquants)


def apply_mapping(row: dict[str, object], mapping: dict[str, str]) -> dict[str, object]:
    """Renomme les clés d'une ligne selon le mapping (en-têtes inconnus conservés
    tels quels — ignorés ensuite par `validate_row` qui lit par nom de champ)."""
    return {mapping.get(key, key): value for key, value in row.items()}


def headers_of(rows: list[dict[str, object]]) -> list[str]:
    """En-têtes présents dans un jeu de lignes (ordre stable, sans doublons)."""
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)
