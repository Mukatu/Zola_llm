"""Résolveur centralisé du dossier `agents/prompts/`.

Ordre de résolution :
1. Variable d'env `ZOLAOS_PROMPTS_DIR` (utilisée en conteneur/prod).
2. Fallback layout source : repo root déduit depuis le path du module.
3. Fallback conteneur par défaut : `/app/agents/prompts`.

Évite le pattern fragile `Path(__file__).resolve().parents[N]` qui casse dès
que le package est installé hors layout source (ex: site-packages).

**Garde-fou IP (Security-IP-1)** : `load_prompt()` refuse de charger un fichier
sous `polaris/` quand `ZOLAOS_PROFILE=box`. C'est une **défense en profondeur** :
en build Zolabox correctement configuré, les fichiers polaris/* ne doivent
PHYSIQUEMENT pas être présents (Security-IP-2). Mais si un attaquant ou un
mauvais déploiement les laisse traîner, ce garde-fou applicatif les rend
inaccessibles depuis le runtime Box. Lève `PolarisPromptForbiddenError`.
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV_VAR = "ZOLAOS_PROMPTS_DIR"
_POLARIS_SUBDIR = "polaris"


class PolarisPromptForbiddenError(PermissionError):
    """Tentative d'accès à un prompt Polaris depuis un profil non-cortex."""


def _candidates() -> list[Path]:
    if env := os.environ.get(_ENV_VAR):
        return [Path(env)]
    # Layout source : src/zolaos/agents/_prompts.py → repo_root/agents/prompts
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "agents" / "prompts",
        Path("/app/agents/prompts"),
    ]


def prompts_dir() -> Path:
    """Retourne le dossier prompts. Lève FileNotFoundError si introuvable."""
    for c in _candidates():
        if c.exists() and c.is_dir():
            return c
    tried = ", ".join(str(c) for c in _candidates())
    raise FileNotFoundError(
        f"Aucun dossier de prompts trouvé. Définis {_ENV_VAR} ou place le "
        f"dossier agents/prompts/ à la racine du repo. Essayé : {tried}"
    )


def _guard_polaris_access(parts: tuple[str, ...]) -> None:
    """Refuse l'accès aux prompts polaris/* en profil non-cortex (Security-IP-1)."""
    if not parts or parts[0] != _POLARIS_SUBDIR:
        return
    # Profil cortex requis. On lit l'env directement pour éviter une dépendance
    # cyclique avec zolaos.core.settings (qui pourrait charger des prompts à l'init).
    profile = os.environ.get("ZOLAOS_PROFILE", "box").lower()
    if profile != "cortex":
        raise PolarisPromptForbiddenError(
            f"Accès interdit au prompt cabinet 'polaris/{'/'.join(parts[1:])}' "
            f"depuis le profil '{profile}'. Les prompts Polaris ne sont accessibles "
            "qu'en profil ZOLAOS_PROFILE=cortex."
        )


def load_prompt(*parts: str) -> str:
    """Lit un prompt et strip le frontmatter YAML s'il existe.

    Lève `PolarisPromptForbiddenError` si on tente de charger `polaris/*`
    depuis un profil autre que `cortex` (défense en profondeur Security-IP-1).
    """
    _guard_polaris_access(parts)
    raw = prompts_dir().joinpath(*parts).read_text(encoding="utf-8")
    if raw.startswith("---"):
        chunks = raw.split("---", 2)
        if len(chunks) >= 3:
            return chunks[2].strip()
    return raw
