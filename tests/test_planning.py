"""Tests du méta-agent Planification."""

from __future__ import annotations

import pytest

from zolaos.agents.meta.planning import Plan, PlanningAgent, PlanningError
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult, LLMClient


class _FakeClient(LLMClient):
    provider = "fake"

    def __init__(self, content: str) -> None:
        self._content = content

    async def generate(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        _ = messages, model, options
        return GenerationResult(content=self._content, model="fake", provider=self.provider)

    async def stream(self, messages, *, model, options=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def health(self) -> bool:
        return True


@pytest.fixture
def settings() -> Settings:
    return Settings()


async def test_simple_query_returns_no_plan(settings: Settings) -> None:
    client = _FakeClient('{"needs_planning":false,"rationale":"trivial","steps":[]}')
    p = PlanningAgent(client=client, settings=settings)
    plan = await p.plan("Quelle heure est-il ?")
    assert plan.needs_planning is False
    assert plan.steps == []


async def test_valid_plan_parses_and_validates_dag(settings: Settings) -> None:
    raw = """
    {
      "needs_planning": true,
      "rationale": "rédaction d'un contrat avec analyse fiscale",
      "steps": [
        {"id":1,"description":"chercher modèle OHADA","agent":"legal","depends_on":[],"expected_output":"modèle"},
        {"id":2,"description":"adapter au droit du travail CG","agent":"legal","depends_on":[1],"expected_output":"draft"},
        {"id":3,"description":"vérifier impact fiscal","agent":"erp","depends_on":[2],"expected_output":"note"}
      ]
    }
    """
    p = PlanningAgent(client=_FakeClient(raw), settings=settings)
    plan = await p.plan("rédige un contrat de prestation OHADA avec analyse fiscale")
    assert plan.needs_planning is True
    assert len(plan.steps) == 3


async def test_cyclic_plan_is_rejected(settings: Settings) -> None:
    raw = """
    {"needs_planning":true,"rationale":"x","steps":[
      {"id":1,"description":"a","agent":"legal","depends_on":[2],"expected_output":"x"},
      {"id":2,"description":"b","agent":"legal","depends_on":[1],"expected_output":"y"}
    ]}
    """
    p = PlanningAgent(client=_FakeClient(raw), settings=settings)
    with pytest.raises(PlanningError):
        await p.plan("hello")
