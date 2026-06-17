"""Wrapper d'appel d'outil — audit + validation centralisée.

Tout outil exposé à un sous-agent passe par `ToolRegistry.invoke()`. Cela
garantit que :
- Chaque appel est loggué (catégorie `tool_call`).
- Les arguments sont validés contre le schéma Pydantic de l'outil.
- L'allowlist par agent est vérifiée.
- Les erreurs sont uniformes.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import orjson
from pydantic import BaseModel, ValidationError

from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL

_log = get_logger("zolaos.tools")


class Tool(ABC):
    """Contrat d'un outil sandboxé."""

    name: str
    description: str
    input_model: type[BaseModel]

    @abstractmethod
    async def run(self, params: BaseModel, *, call_id: uuid.UUID) -> Any:
        """Exécution effective. `params` est déjà validé."""


class ToolError(RuntimeError):
    """Erreur générique d'un outil."""


class ToolNotAllowedError(ToolError):
    """L'agent appelant n'est pas autorisé à utiliser cet outil."""


class ToolInputError(ToolError):
    """Entrée invalide vis-à-vis du schéma de l'outil."""


@dataclass(frozen=True)
class ToolInvocation:
    call_id: uuid.UUID
    tool: str
    agent: str
    input_hash: str
    output_hash: str
    duration_seconds: float
    outcome: str  # ok | error | denied


class ToolRegistry:
    """Catalogue des outils + politique d'allowlist par agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        # Allowlist : `agent_name -> set(tool_names)`. Vide = aucun outil autorisé.
        self._allowlist: dict[str, set[str]] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Outil déjà enregistré : {tool.name}")
        self._tools[tool.name] = tool

    def allow(self, agent: str, *tools: str) -> None:
        unknown = [t for t in tools if t not in self._tools]
        if unknown:
            raise ValueError(f"Outils inconnus dans allow({agent}, ...) : {unknown}")
        self._allowlist.setdefault(agent, set()).update(tools)

    async def invoke(self, *, agent: str, tool_name: str, params: dict[str, Any]) -> tuple[Any, ToolInvocation]:
        call_id = uuid.uuid4()
        start = time.perf_counter()

        # 1. Allowlist
        allowed = self._allowlist.get(agent, set())
        if tool_name not in allowed:
            self._record(agent, tool_name, "denied", params, None, time.perf_counter() - start)
            raise ToolNotAllowedError(
                f"Agent '{agent}' non autorisé à invoquer '{tool_name}' "
                f"(allowed={sorted(allowed)})"
            )

        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolError(f"Outil inconnu : {tool_name}")

        # 2. Validation entrée
        try:
            validated = tool.input_model.model_validate(params)
        except ValidationError as exc:
            self._record(agent, tool_name, "error", params, None, time.perf_counter() - start)
            raise ToolInputError(str(exc)) from exc

        # 3. Exécution + audit
        outcome = "error"
        output: Any = None
        try:
            output = await tool.run(validated, call_id=call_id)
            outcome = "ok"
            return output, self._record(
                agent, tool_name, outcome, params, output, time.perf_counter() - start, call_id=call_id
            )
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent=f"tool.{tool_name}", outcome=outcome).inc()

    @staticmethod
    def _record(
        agent: str,
        tool_name: str,
        outcome: str,
        params: dict[str, Any],
        output: Any,
        duration: float,
        *,
        call_id: uuid.UUID | None = None,
    ) -> ToolInvocation:
        input_hash = hashlib.sha256(orjson.dumps(params, default=str)).hexdigest()
        output_hash = (
            hashlib.sha256(orjson.dumps(output, default=str)).hexdigest()
            if output is not None
            else ""
        )
        inv = ToolInvocation(
            call_id=call_id or uuid.uuid4(),
            tool=tool_name,
            agent=agent,
            input_hash=input_hash,
            output_hash=output_hash,
            duration_seconds=duration,
            outcome=outcome,
        )
        _log.info(
            "tool.call",
            tool=tool_name,
            agent=agent,
            outcome=outcome,
            input_hash=input_hash,
            output_hash=output_hash,
            duration_seconds=duration,
            call_id=str(inv.call_id),
        )
        return inv
