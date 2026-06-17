"""Méta-agent Planification — décompose une requête complexe en sous-tâches.

Pattern : Plan-and-Execute. Le plan est ensuite consommé par l'Orchestrateur
qui dispatche les étapes aux sous-agents (parallèle quand possible).
"""

from __future__ import annotations

import orjson
from pydantic import BaseModel, Field, ValidationError

from zolaos.agents._prompts import load_prompt
from zolaos.agents.router import Pole
from zolaos.core.logging import get_logger
from zolaos.core.metrics import AGENT_INVOCATIONS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationOptions, LLMClient, Message

_log = get_logger("zolaos.agents.meta.planning")


_SYSTEM_PROMPT_CACHE: str | None = None


def _system_prompt() -> str:
    global _SYSTEM_PROMPT_CACHE  # noqa: PLW0603
    if _SYSTEM_PROMPT_CACHE is None:
        _SYSTEM_PROMPT_CACHE = load_prompt("meta", "planning.md")
    return _SYSTEM_PROMPT_CACHE


class PlanStep(BaseModel):
    id: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=500)
    agent: Pole
    depends_on: list[int] = Field(default_factory=list)
    expected_output: str = Field(min_length=1, max_length=500)


class Plan(BaseModel):
    needs_planning: bool
    rationale: str = ""
    steps: list[PlanStep] = Field(default_factory=list)

    def validate_dag(self) -> None:
        """Vérifie que `depends_on` ne forme pas de cycle et référence des id valides."""
        ids = {s.id for s in self.steps}
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in ids:
                    raise PlanningError(f"Étape {step.id} dépend de l'id inconnu {dep}")
                if dep >= step.id:
                    raise PlanningError(
                        f"Étape {step.id} dépend de {dep} (>= elle-même → cycle ou avant)"
                    )


class PlanningError(RuntimeError):
    """Plan retourné par le LLM non parseable ou cyclique."""


class PlanningAgent:
    """Méta-agent Planification."""

    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def plan(self, user_query: str) -> Plan:
        messages = [
            Message(role="system", content=_system_prompt()),
            Message(role="user", content=user_query),
        ]
        options = GenerationOptions(
            temperature=0.1,
            max_tokens=1024,
            json_mode=True,
            json_schema=Plan.model_json_schema(),
        )

        outcome = "error"
        try:
            result = await self._client.generate(
                messages,
                model=self._settings.LLM_MODEL_CORE,
                options=options,
            )
            plan = self._parse(result.content)
            plan.validate_dag()
            outcome = "ok"
            _log.info(
                "planning.plan",
                needs_planning=plan.needs_planning,
                num_steps=len(plan.steps),
                duration_seconds=result.duration_seconds,
            )
            return plan
        finally:
            AGENT_INVOCATIONS_TOTAL.labels(agent="planning", outcome=outcome).inc()

    @staticmethod
    def _parse(raw: str) -> Plan:
        text = raw.strip()
        if "```" in text:
            first = text.find("{")
            last = text.rfind("}")
            if first >= 0 and last > first:
                text = text[first : last + 1]
        try:
            data = orjson.loads(text)
        except orjson.JSONDecodeError as exc:
            raise PlanningError(f"Sortie LLM non-JSON : {raw[:200]!r}") from exc
        try:
            return Plan.model_validate(data)
        except ValidationError as exc:
            raise PlanningError(f"Sortie LLM invalide : {exc}") from exc
