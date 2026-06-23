"""Tests du routeur — parsing JSON robuste, sans appel LLM réel."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from zolaos.agents.router import Pole, Router, RouterError
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
        _ = messages, model, options

        async def _gen() -> AsyncIterator[str]:
            yield self._content

        return _gen()

    async def health(self) -> bool:
        return True


@pytest.fixture
def settings() -> Settings:
    return Settings()


async def test_router_parses_clean_json(settings: Settings) -> None:
    client = _FakeClient(
        '{"pole":"health","module":"pharmacology","confidence":0.92,"language":"fr","country_hint":"cg","complexity":"simple","warning":null}'
    )
    r = Router(client=client, settings=settings)
    decision = await r.classify("Quelle est la posologie du paracétamol pour un enfant de 6 ans ?")
    assert decision.pole == Pole.HEALTH
    assert decision.module == "pharmacology"
    assert decision.confidence == 0.92
    assert decision.warning is None


async def test_router_strips_markdown_fences(settings: Settings) -> None:
    client = _FakeClient(
        '```json\n{"pole":"legal","module":"ohada","confidence":0.8,"language":"fr","country_hint":"cg","complexity":"moderate","warning":null}\n```'
    )
    r = Router(client=client, settings=settings)
    decision = await r.classify("Rédige un contrat de bail OHADA.")
    assert decision.pole == Pole.LEGAL
    assert decision.module == "ohada"


async def test_router_rejects_invalid_json(settings: Settings) -> None:
    client = _FakeClient("désolé je ne sais pas")
    r = Router(client=client, settings=settings)
    with pytest.raises(RouterError):
        await r.classify("blabla")


async def test_router_rejects_invalid_schema(settings: Settings) -> None:
    client = _FakeClient('{"pole":"unknown_pole","confidence":2.5}')
    r = Router(client=client, settings=settings)
    with pytest.raises(RouterError):
        await r.classify("blabla")
