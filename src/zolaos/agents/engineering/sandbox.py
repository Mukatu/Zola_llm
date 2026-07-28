"""Runner d'exécution de code en sandbox (Pôle Engineering, profil box).

Exécute du code généré par l'assistant code (`code.py`) dans un conteneur
Docker **jetable et durci**, piloté via le socket Docker de la box. C'est une
pièce SÉCURITÉ : le rayon de souffle en cas de code malveillant/buggé doit se
limiter au conteneur jetable — aucun accès réseau, dépôt, DB ou secrets.

Désactivée par défaut (`CODE_SANDBOX_ENABLED=False`) : exécuter du code généré
est sensible, le client l'active explicitement (cf. `Settings`).

Isolation appliquée (invariants, pas des suggestions) :
- `--network none` : aucun accès réseau depuis le conteneur.
- `--user 65534:65534` : exécution non-root (nobody).
- `--read-only` + `--tmpfs /tmp` : rootfs immuable, seul `/tmp` est inscriptible
  (RAM, taille bornée) — le programme décodé y est écrit avant exécution.
- `--memory` / `--memory-swap` (égaux → swap désactivé) / `--cpus` /
  `--pids-limit` : bornes de ressources (fork bombs, OOM voisins).
- `--cap-drop ALL` + `--security-opt no-new-privileges` : aucune capability
  Linux, pas d'élévation de privilèges (setuid, etc.).
- `--rm` : conteneur jetable, jamais réutilisé.

Le code source est transmis via la variable d'environnement `CODE_B64`
(base64), jamais interpolé dans une ligne de commande shell : évite toute
injection shell via le contenu du code.
"""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings

_log = get_logger("zolaos.agents.engineering.sandbox")

# Borne dure : quel que soit `timeout_seconds` demandé par l'appelant, on ne
# laisse jamais un conteneur tourner plus longtemps que ça.
_HARD_TIMEOUT_MAX_SECONDS = 60

#: Allowlist des langages supportés → (image Docker, interpréteur dans l'image).
LANG_IMAGES: dict[str, tuple[str, str]] = {
    "python": ("python:3.12-slim", "python"),
    "javascript": ("node:20-slim", "node"),
    "bash": ("bash:5", "bash"),
}


class SandboxDisabledError(Exception):
    """Levée quand `CODE_SANDBOX_ENABLED` est False (défaut)."""


class SandboxLanguageError(Exception):
    """Levée quand le langage demandé n'est pas dans `LANG_IMAGES`."""


@dataclass(frozen=True)
class RunResult:
    """Résultat d'une exécution en sandbox."""

    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    duration_seconds: float


def _truncate(data: bytes, max_bytes: int) -> str:
    """Décode en UTF-8 (remplacement des octets invalides) et tronque à `max_bytes`."""
    return data[:max_bytes].decode("utf-8", errors="replace")


async def _force_remove_container(name: str) -> None:
    """Best-effort `docker rm -f <name>` après un timeout. N'échoue jamais
    (le conteneur peut déjà être parti, docker peut être indisponible)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception as exc:  # pragma: no cover — best-effort, jamais fatal
        _log.warning("sandbox.force_remove_failed", container=name, error=str(exc))


async def run_code(
    language: str,
    code: str,
    *,
    settings: Settings,
    timeout_seconds: int | None = None,
) -> RunResult:
    """Exécute `code` dans un conteneur Docker jetable et durci.

    Args:
        language: langage cible, doit figurer dans `LANG_IMAGES` (insensible à la casse).
        code: code source à exécuter. Jamais loggué.
        settings: configuration (sandbox activée ?, limites de ressources).
        timeout_seconds: délai max avant kill. Défaut `settings.CODE_SANDBOX_TIMEOUT_SECONDS`,
            borné dans tous les cas par `_HARD_TIMEOUT_MAX_SECONDS`.

    Raises:
        SandboxDisabledError: si `settings.CODE_SANDBOX_ENABLED` est False.
        SandboxLanguageError: si `language` n'est pas supporté.
    """
    if not settings.CODE_SANDBOX_ENABLED:
        raise SandboxDisabledError(
            "La sandbox d'exécution de code est désactivée (CODE_SANDBOX_ENABLED=False)."
        )

    lang = language.lower()
    if lang not in LANG_IMAGES:
        raise SandboxLanguageError(
            f"Langage non supporté : {language!r}. Langages autorisés : {sorted(LANG_IMAGES)}."
        )
    image, interpreter = LANG_IMAGES[lang]

    requested_timeout = (
        timeout_seconds if timeout_seconds is not None else settings.CODE_SANDBOX_TIMEOUT_SECONDS
    )
    timeout = min(requested_timeout, _HARD_TIMEOUT_MAX_SECONDS)
    code_b64 = base64.b64encode(code.encode()).decode("ascii")
    container_name = f"zolaos-sbx-{uuid.uuid4().hex}"

    shell_cmd = f'printf %s "$CODE_B64" | base64 -d > /tmp/prog && exec {interpreter} /tmp/prog'

    args = [
        "run",
        "--rm",
        "-i",
        "--name",
        container_name,
        "--network",
        "none",
        "--user",
        "65534:65534",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=64m,mode=1777",  # noqa: S108 (tmpfs *dans* le conteneur jetable, volontaire)
        "--memory",
        settings.CODE_SANDBOX_MEMORY,
        "--memory-swap",
        settings.CODE_SANDBOX_MEMORY,
        "--cpus",
        settings.CODE_SANDBOX_CPUS,
        "--pids-limit",
        str(settings.CODE_SANDBOX_PIDS_LIMIT),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-e",
        f"CODE_B64={code_b64}",
        image,
        "sh",
        "-c",
        shell_cmd,
    ]

    start = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await _force_remove_container(container_name)
        duration = time.perf_counter() - start
        _log.warning(
            "sandbox.run_timeout",
            language=lang,
            timeout_seconds=timeout,
            duration_seconds=duration,
        )
        return RunResult(
            stdout="",
            stderr="",
            exit_code=None,
            timed_out=True,
            duration_seconds=duration,
        )

    duration = time.perf_counter() - start
    max_bytes = settings.CODE_SANDBOX_OUTPUT_MAX_BYTES
    result = RunResult(
        stdout=_truncate(stdout_bytes, max_bytes),
        stderr=_truncate(stderr_bytes, max_bytes),
        exit_code=proc.returncode,
        timed_out=False,
        duration_seconds=duration,
    )
    _log.info(
        "sandbox.run_completed",
        language=lang,
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        duration_seconds=result.duration_seconds,
    )
    return result
