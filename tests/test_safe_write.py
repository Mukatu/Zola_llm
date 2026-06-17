"""Tests Safe Write — au cœur de la sécurité des agents."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from zolaos.tools.base import ToolNotAllowedError, ToolRegistry
from zolaos.tools.safe_write import SafeWriteParams, SafeWriteTool


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def registry(workspace: Path) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(SafeWriteTool(allowed_workspaces=[workspace]))
    reg.allow("brigade.engineering", "safe_write")
    return reg


@pytest.mark.security
async def test_write_inside_workspace_ok(registry: ToolRegistry, workspace: Path) -> None:
    out, inv = await registry.invoke(
        agent="brigade.engineering",
        tool_name="safe_write",
        params={"path": str(workspace / "hello.txt"), "content": "bonjour"},
    )
    assert inv.outcome == "ok"
    assert (workspace / "hello.txt").read_text() == "bonjour"


@pytest.mark.security
async def test_write_outside_workspace_refused(registry: ToolRegistry, tmp_path: Path) -> None:
    other = tmp_path / "elsewhere.txt"
    with pytest.raises(Exception):  # ToolError
        await registry.invoke(
            agent="brigade.engineering",
            tool_name="safe_write",
            params={"path": str(other), "content": "x"},
        )
    assert not other.exists()


@pytest.mark.security
async def test_write_forbidden_extension_refused(registry: ToolRegistry, workspace: Path) -> None:
    with pytest.raises(Exception):
        await registry.invoke(
            agent="brigade.engineering",
            tool_name="safe_write",
            params={"path": str(workspace / "secret.env"), "content": "X=1"},
        )


@pytest.mark.security
async def test_write_forbidden_filename_refused(registry: ToolRegistry, workspace: Path) -> None:
    with pytest.raises(Exception):
        await registry.invoke(
            agent="brigade.engineering",
            tool_name="safe_write",
            params={"path": str(workspace / "id_rsa"), "content": "X"},
        )


@pytest.mark.security
async def test_agent_not_in_allowlist_refused(registry: ToolRegistry, workspace: Path) -> None:
    with pytest.raises(ToolNotAllowedError):
        await registry.invoke(
            agent="brigade.health",  # pas autorisé sur safe_write
            tool_name="safe_write",
            params={"path": str(workspace / "x.txt"), "content": "y"},
        )


@pytest.mark.security
async def test_no_overwrite_by_default(registry: ToolRegistry, workspace: Path) -> None:
    (workspace / "f.txt").write_text("existing")
    with pytest.raises(Exception):
        await registry.invoke(
            agent="brigade.engineering",
            tool_name="safe_write",
            params={"path": str(workspace / "f.txt"), "content": "new"},
        )


@pytest.mark.security
async def test_input_validation_rejects_bad_params(registry: ToolRegistry) -> None:
    from zolaos.tools.base import ToolInputError

    with pytest.raises(ToolInputError):
        await registry.invoke(
            agent="brigade.engineering",
            tool_name="safe_write",
            params={"path": "", "content": "y"},  # path vide
        )


def test_safe_write_params_model_size_limit() -> None:
    """Le schéma Pydantic refuse une charge utile > 5 Mo."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SafeWriteParams(path="x.txt", content="a" * 6_000_000)
