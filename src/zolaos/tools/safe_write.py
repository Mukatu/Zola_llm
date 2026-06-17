"""Safe Write — validateur centralisé d'écriture fichier.

Aucun sous-agent n'écrit jamais directement sur disque. Tout passe par cet
outil, qui vérifie :
- l'allowlist de workspaces autorisés ;
- l'absence de traversée (`..`, liens symboliques pointant hors zone) ;
- l'absence d'extension dangereuse (`.env`, `.key`, `.pem`, `id_rsa`, etc.) ;
- la taille maximale autorisée.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from zolaos.core.logging import get_logger
from zolaos.tools.base import Tool, ToolError

_log = get_logger("zolaos.tools.safe_write")

# Extensions interdites en écriture, peu importe l'allowlist.
FORBIDDEN_EXTENSIONS = frozenset(
    {".env", ".key", ".pem", ".p12", ".pfx", ".gpg", ".asc"}
)

FORBIDDEN_FILENAMES = frozenset(
    {"id_rsa", "id_ed25519", ".htaccess", ".htpasswd", ".npmrc", ".pypirc"}
)


class SafeWriteParams(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=5_000_000)  # 5 Mo
    overwrite: bool = False


class SafeWriteTool(Tool):
    name = "safe_write"
    description = "Écrit un fichier dans un workspace autorisé. Refuse les chemins sensibles."
    input_model = SafeWriteParams

    def __init__(self, allowed_workspaces: list[Path]) -> None:
        if not allowed_workspaces:
            raise ValueError("SafeWriteTool exige au moins un workspace autorisé.")
        # Résolution + normalisation des workspaces.
        self._allowed = [w.resolve(strict=False) for w in allowed_workspaces]

    async def run(self, params: SafeWriteParams, *, call_id: uuid.UUID) -> dict[str, object]:
        target = Path(params.path)
        # Résoudre sans suivre les symlinks pour le check, puis re-résoudre strictement.
        resolved = target.resolve(strict=False)

        # 1. Doit être dans un workspace autorisé.
        if not any(self._is_inside(resolved, ws) for ws in self._allowed):
            raise ToolError(f"safe_write refusé : chemin hors workspace ({resolved}).")

        # 2. Pas de fichier sensible.
        if resolved.name in FORBIDDEN_FILENAMES:
            raise ToolError(f"safe_write refusé : nom de fichier interdit ({resolved.name}).")
        if resolved.suffix.lower() in FORBIDDEN_EXTENSIONS:
            raise ToolError(f"safe_write refusé : extension interdite ({resolved.suffix}).")

        # 3. Pas d'écrasement silencieux.
        if resolved.exists() and not params.overwrite:
            raise ToolError(f"safe_write refusé : fichier existant et overwrite=false.")

        # 4. Création des dossiers parents (uniquement à l'intérieur du workspace).
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 5. Écriture
        resolved.write_text(params.content, encoding="utf-8")
        bytes_written = os.path.getsize(resolved)
        _log.info(
            "safe_write.done",
            call_id=str(call_id),
            path=str(resolved),
            bytes=bytes_written,
        )
        return {"path": str(resolved), "bytes_written": bytes_written}

    @staticmethod
    def _is_inside(child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
