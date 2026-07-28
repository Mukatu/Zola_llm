"""Tests du runner sandbox d'exécution de code (Pôle Engineering).

AUCUN vrai Docker n'est invoqué : `asyncio.create_subprocess_exec` est
monkeypatché. Couvre :
- garde-fou `CODE_SANDBOX_ENABLED=False` (défaut) → erreur AVANT tout Docker
- langage inconnu → erreur
- invariants de sécurité : tous les drapeaux d'isolation Docker sont présents,
  le code ne fuite jamais en clair dans les arguments (base64 uniquement)
- exécution nominale (stdout/stderr/exit_code)
- timeout → kill + `docker rm -f` best-effort
- troncature de la sortie
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field

import pytest

from zolaos.agents.engineering import sandbox as sandbox_mod
from zolaos.agents.engineering.sandbox import (
    RunResult,
    SandboxDisabledError,
    SandboxLanguageError,
    run_code,
)
from zolaos.core.settings import Settings


def _settings(**overrides: object) -> Settings:
    """Settings valides pour les tests (secrets requis non vides)."""
    defaults: dict[str, object] = {
        "POSTGRES_PASSWORD_APP": "x",
        "POSTGRES_PASSWORD_MIGRATIONS": "x",
        "JWT_SECRET": "x" * 32,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _enabled_settings(**overrides: object) -> Settings:
    return _settings(CODE_SANDBOX_ENABLED=True, **overrides)


@dataclass
class _FakeProcess:
    """Simule un `asyncio.subprocess.Process` pour les tests."""

    stdout_data: bytes = b""
    stderr_data: bytes = b""
    returncode: int | None = 0
    _communicate_hang: bool = False
    killed: bool = field(default=False, init=False)

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._communicate_hang:
            # Ne rend jamais la main : simule un conteneur qui tourne indéfiniment.
            # `asyncio.wait_for` doit couper court via son propre timeout.
            await asyncio.Event().wait()
        return self.stdout_data, self.stderr_data

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return 0


# =============================================================================
# Garde-fous : sandbox désactivée / langage inconnu
# =============================================================================


@pytest.mark.asyncio
async def test_sandbox_disabled_by_default_raises_before_any_docker_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def _spy(*args: object, **kwargs: object) -> _FakeProcess:
        nonlocal called
        called = True
        return _FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)

    settings = _settings()  # CODE_SANDBOX_ENABLED=False par défaut
    assert settings.CODE_SANDBOX_ENABLED is False

    with pytest.raises(SandboxDisabledError):
        await run_code("python", "print(1)", settings=settings)

    assert called is False  # jamais d'appel Docker


@pytest.mark.asyncio
async def test_unknown_language_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _spy(*args: object, **kwargs: object) -> _FakeProcess:
        raise AssertionError("ne doit pas être appelé pour un langage inconnu")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)

    settings = _enabled_settings()
    with pytest.raises(SandboxLanguageError):
        await run_code("cobol", "IDENTIFICATION DIVISION.", settings=settings)


# =============================================================================
# Invariants de sécurité
# =============================================================================


@pytest.mark.asyncio
async def test_docker_run_flags_enforce_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_args: list[str] = []

    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        assert program == "docker"
        captured_args.extend(args)
        return _FakeProcess(stdout_data=b"ok\n", stderr_data=b"", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    settings = _enabled_settings()
    secret_code = "print('SECRET_MARKER_42')"
    result = await run_code("python", secret_code, settings=settings)

    assert result.exit_code == 0

    # Tous les drapeaux d'isolation obligatoires sont présents.
    required_flags = [
        "--network",
        "--cap-drop",
        "--read-only",
        "--user",
        "--security-opt",
        "--memory",
        "--pids-limit",
        "--rm",
    ]
    for flag in required_flags:
        assert flag in captured_args, f"drapeau manquant : {flag}"

    assert "none" in captured_args  # --network none
    assert "ALL" in captured_args  # --cap-drop ALL
    assert "65534:65534" in captured_args  # --user nobody
    assert "no-new-privileges" in captured_args

    # Le code ne doit JAMAIS apparaître en clair dans les arguments (injection shell).
    joined = " ".join(captured_args)
    assert secret_code not in joined
    assert "SECRET_MARKER_42" not in joined

    # Il doit être présent en base64 dans la variable d'env CODE_B64.
    expected_b64 = base64.b64encode(secret_code.encode()).decode("ascii")
    assert f"CODE_B64={expected_b64}" in captured_args


@pytest.mark.asyncio
async def test_memory_swap_equals_memory_and_cpus_pids_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_args: list[str] = []

    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        captured_args.extend(args)
        return _FakeProcess(stdout_data=b"", stderr_data=b"", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    settings = _enabled_settings(
        CODE_SANDBOX_MEMORY="512m",
        CODE_SANDBOX_CPUS="1.0",
        CODE_SANDBOX_PIDS_LIMIT=64,
    )
    await run_code("python", "pass", settings=settings)

    mem_indices = [i for i, a in enumerate(captured_args) if a == "--memory"]
    swap_indices = [i for i, a in enumerate(captured_args) if a == "--memory-swap"]
    assert captured_args[mem_indices[0] + 1] == "512m"
    assert captured_args[swap_indices[0] + 1] == "512m"  # swap désactivé (== memory)

    cpus_idx = captured_args.index("--cpus")
    assert captured_args[cpus_idx + 1] == "1.0"

    pids_idx = captured_args.index("--pids-limit")
    assert captured_args[pids_idx + 1] == "64"


# =============================================================================
# Exécution nominale
# =============================================================================


@pytest.mark.asyncio
async def test_nominal_run_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(stdout_data=b"hello\n", stderr_data=b"", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    settings = _enabled_settings()
    result = await run_code("python", "print('hello')", settings=settings)

    assert isinstance(result, RunResult)
    assert result.stdout == "hello\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.duration_seconds >= 0.0


@pytest.mark.asyncio
async def test_nominal_run_with_nonzero_exit_and_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(
            stdout_data=b"",
            stderr_data=b"Traceback...\n",
            returncode=1,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    settings = _enabled_settings()
    result = await run_code("python", "raise ValueError()", settings=settings)

    assert result.exit_code == 1
    assert "Traceback" in result.stderr
    assert result.timed_out is False


# =============================================================================
# Timeout
# =============================================================================


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_timed_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_proc = _FakeProcess(_communicate_hang=True)
    remove_calls: list[str] = []

    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        return fake_proc

    async def _fake_force_remove(name: str) -> None:
        remove_calls.append(name)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(sandbox_mod, "_force_remove_container", _fake_force_remove)

    settings = _enabled_settings(CODE_SANDBOX_TIMEOUT_SECONDS=1)
    result = await run_code("python", "while True: pass", settings=settings)

    assert result.timed_out is True
    assert result.exit_code is None
    assert fake_proc.killed is True
    assert len(remove_calls) == 1
    assert remove_calls[0].startswith("zolaos-sbx-")


# =============================================================================
# Troncature de la sortie
# =============================================================================


@pytest.mark.asyncio
async def test_output_truncated_to_max_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    big_stdout = b"x" * 1000

    async def _fake_exec(program: str, *args: str, **kwargs: object) -> _FakeProcess:
        return _FakeProcess(stdout_data=big_stdout, stderr_data=b"", returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

    settings = _enabled_settings(CODE_SANDBOX_OUTPUT_MAX_BYTES=100)
    result = await run_code("python", "print('x' * 1000)", settings=settings)

    assert len(result.stdout) == 100
