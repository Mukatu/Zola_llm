"""Augmentation LLM **optionnelle** du mapping de colonnes (IMP-3).

Strictement complémentaire au moteur déterministe : on ne sollicite le LLM que
pour les en-têtes que la similarité n'a pas résolus, et uniquement pour
**proposer** un champ (jamais pour valider une donnée). Tolérant aux pannes :
toute erreur (LLM indisponible, JSON invalide, champ inconnu) → suggestions vides.
"""

from __future__ import annotations

import json
from typing import Any

from zolaos.imports.framework import EntitySpec
from zolaos.llm.base import GenerationOptions, Message

_SYS = (
    "Tu es un assistant d'intégration de données. On te donne des en-têtes de "
    "colonnes d'un fichier Excel et la liste des champs cibles attendus. Pour "
    "chaque en-tête, indique le champ cible le plus probable, ou null si aucun "
    "ne correspond. Réponds UNIQUEMENT en JSON: un objet {en-tête: champ|null}."
)


def _prompt(spec: EntitySpec, headers: list[str], champs: list[str]) -> str:
    lignes = [f"- {c.name}: {c.help or c.name}" for c in spec.columns if c.name in champs]
    return (
        f"Entité: {spec.label}\n"
        f"Champs cibles disponibles:\n" + "\n".join(lignes) + "\n\n"
        f"En-têtes à rapprocher: {json.dumps(headers, ensure_ascii=False)}\n"
        "Renvoie l'objet JSON de mapping."
    )


async def suggest_mapping(
    client: Any,
    model: str,
    spec: EntitySpec,
    headers_non_resolus: list[str],
    champs_disponibles: list[str],
) -> dict[str, str]:
    """Propose un champ pour chaque en-tête non résolu. Jamais d'exception."""
    if not headers_non_resolus or not champs_disponibles:
        return {}
    valides = {c.name for c in spec.columns if c.name in set(champs_disponibles)}
    try:
        result = await client.generate(
            [
                Message(role="system", content=_SYS),
                Message(
                    role="user",
                    content=_prompt(spec, headers_non_resolus, champs_disponibles),
                ),
            ],
            model=model,
            options=GenerationOptions(temperature=0.0, json_mode=True, max_tokens=512),
        )
        data = json.loads(result.content)
    except Exception:
        return {}
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for header, champ in data.items():
            if header in headers_non_resolus and isinstance(champ, str) and champ in valides:
                out[header] = champ
    return out
