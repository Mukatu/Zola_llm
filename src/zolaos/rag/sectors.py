"""Détection déterministe du secteur d'activité d'une requête.

Les conventions collectives sectorielles (droit du travail CG) sont taguées
``secteur:<x>`` dans ``rag_legal``. Quand une question nomme un secteur (« dans
le secteur bancaire »), on veut ancrer la réponse sur la convention DE CE
secteur, pas sur un mélange de toutes les conventions (qui se ressemblent
sémantiquement). Ce module fait cette détection **sans LLM** : une simple carte
mots-clés → secteur, sur le texte normalisé (minuscules, accents retirés).

Seuls les 14 secteurs **réellement présents dans le corpus** sont mappés — un
mot-clé sans convention ingérée ne sert à rien.
"""

from __future__ import annotations

import re
import unicodedata

# secteur (= valeur du tag `secteur:<x>`) → mots-clés déclencheurs (sans accent).
# Ordre important : le premier secteur dont un mot-clé apparaît l'emporte, donc
# on met les termes non ambigus en tête de chaque liste.
_SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "banque": ("banque", "bancaire", "banquier"),
    "mines": ("mine", "minier", "miniere", "extractif", "extractive"),
    "hotellerie": ("hotel", "hotellerie", "restauration", "catering", "hebergement"),
    "aerien": ("aerien", "aerienne", "aviation", "aeroport", "navigant"),
    "peche": ("peche", "pecheur", "halieutique", "maritime industrielle"),
    "transport": ("transport", "logistique", "auxiliaire de transport", "routier"),
    "agriculture": ("agricole", "agriculture", "agro", "plantation"),
    "boulangerie": ("boulangerie", "boulanger", "patisserie"),
    "foret": ("forestier", "forestiere", "foret", "exploitation forestiere", "grumier"),
    "pharmacie": ("pharmacie", "officine", "pharmacien"),
    "domestique": ("domestique", "gens de maison", "employe de maison", "gardiennage"),
    "tic": ("ntic", "telecom", "telecommunication", "informatique", "numerique"),
    "industrie": ("industrie", "industriel", "manufacture", "usine"),
    "commerce": ("commerce", "commercant", "grande distribution"),
}


def _normalize(text: str) -> str:
    """Minuscules + suppression des accents (comparaison robuste)."""
    n = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def detect_sector(query: str) -> str | None:
    """Secteur d'activité nommé par la requête, ou None.

    Retourne la valeur de tag (« banque », « mines »…) telle qu'utilisée dans le
    corpus. Le mot-clé est cherché comme mot entier (frontières \\b) pour éviter
    les faux positifs (« minier » ne doit pas matcher dans « administratif »).
    """
    norm = _normalize(query)
    for sector, keywords in _SECTOR_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", norm):
                return sector
    return None


__all__ = ["detect_sector"]
