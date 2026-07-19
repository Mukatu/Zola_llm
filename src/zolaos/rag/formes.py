"""Détection déterministe de la forme juridique de société visée par une requête.

Les articles OHADA sont tagués `forme:<x>` (sarl, sa, sas, snc, scs, gie,
societe_participation, cooperative) à l'ingestion (scripts/ingest_ohada.py). Une
question sur une SARL ne doit pas se faire ancrer sur les articles des sociétés
COOPÉRATIVES (autre Acte uniforme, texte mieux océrisé qui ressort à tort). Ce
module détecte la forme SANS LLM — carte mots-clés sur le texte normalisé — pour
que l'agent OHADA boost la bonne forme et écarte les autres (cf. le boost secteur
de `sectors.py`, même mécanique).

Les valeurs retournées correspondent EXACTEMENT aux tags posés à l'ingestion.
"""

from __future__ import annotations

import re
import unicodedata

# forme (= valeur du tag `forme:<x>`) → mots-clés déclencheurs (sans accent).
# Ordre : les formes les plus spécifiques d'abord (une requête ne nomme en général
# qu'une forme). On évite les abréviations trop courtes et ambiguës (« SA » seul,
# « participation » seul) au profit des libellés complets.
_FORME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sarl": ("sarl", "societe a responsabilite limitee", "responsabilite limitee"),
    "sas": ("sas", "societe par actions simplifiee", "actions simplifiee"),
    "snc": ("snc", "societe en nom collectif", "nom collectif"),
    "scs": ("scs", "societe en commandite", "commandite"),
    "gie": ("gie", "groupement d interet economique", "groupement d'interet economique"),
    "societe_participation": ("societe en participation",),
    "cooperative": ("cooperative", "cooperatives", "societe cooperative"),
    "sa": ("societe anonyme",),  # jamais l'abréviation « sa » seule (trop ambiguë)
}


def _normalize(text: str) -> str:
    n = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def detect_forme_juridique(query: str) -> str | None:
    """Forme juridique de société nommée par la requête, ou None.

    Retourne la valeur de tag (« sarl », « cooperative »…) telle qu'utilisée dans
    le corpus. Mot entier (frontières \\b) pour éviter les faux positifs.
    """
    norm = _normalize(query)
    for forme, keywords in _FORME_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", norm):
                return forme
    return None


__all__ = ["detect_forme_juridique"]
