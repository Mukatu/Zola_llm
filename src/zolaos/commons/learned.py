"""Règles apprises déterministes (multi-métier) — clé normalisée + lookup.

`(domaine, cle) -> valeur`. La `cle` est **normalisée puis anonymisée** (même
transform à la capture et à la consultation → correspondance cohérente ; les
identifiants deviennent des jetons stables des deux côtés).
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.commons.anonymize import anonymize
from zolaos.db.store_models import LearnedRule


def normalize(texte: str) -> str:
    """Minuscule, sans accents, espaces normalisés."""
    nfkd = unicodedata.normalize("NFKD", (texte or "").lower())
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sans_accents.split())


def rule_key(texte: str) -> str:
    """Clé de correspondance : normalisée **et** anonymisée (jamais d'identifiant brut)."""
    return anonymize(normalize(texte))


async def lookup(session: AsyncSession, domaine: str, texte: str) -> list[LearnedRule]:
    """Règles apprises applicables à `texte` : clé exacte OU contenue (plus spécifique d'abord)."""
    key = rule_key(texte)
    if not key:
        return []
    rows = (
        (await session.execute(select(LearnedRule).where(LearnedRule.domaine == domaine)))
        .scalars()
        .all()
    )
    hits = [r for r in rows if r.cle and (r.cle == key or r.cle in key)]
    hits.sort(key=lambda r: (len(r.cle), r.occurrences), reverse=True)
    return hits
