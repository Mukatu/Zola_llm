"""Tests du sous-agent Code Agent (Engineering-1).

Mock LLM client — pas d'appel réel. Couvre :
- chargement du prompt
- mode conversationnel (réponse libre)
- mode structured_output (parsing CodeArtifact)
- robustesse parsing si le LLM renvoie du JSON invalide
- propagation `intent`, `language_hint`, `force_model`
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zolaos.agents.engineering.code import CodeAgent, CodeArtifact
from zolaos.core.settings import Settings
from zolaos.llm.base import GenerationResult


@pytest.fixture
def settings() -> Settings:
    return Settings()


def test_prompt_loads_and_mentions_code_intents(settings: Settings) -> None:
    fake_llm = AsyncMock()
    agent = CodeAgent(client=fake_llm, settings=settings)
    prompt = agent._system_prompt
    assert "engineering.code" in prompt
    # Doit mentionner les 6 intents supportés
    for intent in ("generate", "refactor", "debug", "explain", "review", "test"):
        assert intent in prompt.lower(), f"intent '{intent}' manquant dans le prompt"


@pytest.mark.asyncio
async def test_conversational_mode_returns_free_text(settings: Settings) -> None:
    fake_llm = AsyncMock()
    fake_llm.generate.return_value = GenerationResult(
        content="```python\ndef hello():\n    return 'world'\n```",
        model="llama-3-8b",
        provider="llamacpp",
    )
    agent = CodeAgent(client=fake_llm, settings=settings)

    response = await agent.answer("Écris une fonction hello en Python", intent="generate")

    assert response.agent == "engineering.code"
    assert response.intent == "generate"
    assert "hello" in response.content
    assert response.artifact is None  # mode conversationnel : pas d'artifact parsé

    # Vérifie que le prompt système et user_msg ont bien été envoyés
    fake_llm.generate.assert_called_once()
    call_args = fake_llm.generate.call_args
    messages = call_args.args[0]
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "[Intent] generate" in messages[1].content


@pytest.mark.asyncio
async def test_structured_output_parses_artifact(settings: Settings) -> None:
    expected = CodeArtifact(
        language="python",
        code="def add(a: int, b: int) -> int:\n    return a + b",
        explanation="Fonction add simple, typage explicite.",
        suggested_tests=["assert add(2, 3) == 5"],
        warnings=["Aucun"],
    )

    fake_llm = AsyncMock()
    fake_llm.generate.return_value = GenerationResult(
        content=expected.model_dump_json(),
        model="llama-3-8b",
        provider="llamacpp",
    )
    agent = CodeAgent(client=fake_llm, settings=settings)

    response = await agent.answer(
        "Écris add(a,b)",
        intent="generate",
        structured_output=True,
    )

    assert response.artifact is not None
    assert response.artifact.language == "python"
    assert "def add" in response.artifact.code
    assert len(response.artifact.suggested_tests) == 1

    # Vérifie que json_mode + json_schema ont bien été passés au LLM
    opts = fake_llm.generate.call_args.kwargs["options"]
    assert opts.json_mode is True
    assert opts.json_schema is not None
    assert "language" in opts.json_schema["properties"]


@pytest.mark.asyncio
async def test_structured_output_robust_to_invalid_json(settings: Settings) -> None:
    """Si le LLM renvoie du JSON invalide en structured_output, on garde le brut + artifact=None."""
    fake_llm = AsyncMock()
    fake_llm.generate.return_value = GenerationResult(
        content="ce n'est pas du JSON",
        model="llama-3-8b",
        provider="llamacpp",
    )
    agent = CodeAgent(client=fake_llm, settings=settings)

    response = await agent.answer("?", intent="generate", structured_output=True)

    assert response.artifact is None
    assert response.content == "ce n'est pas du JSON"


@pytest.mark.asyncio
async def test_force_model_overrides_default(settings: Settings) -> None:
    fake_llm = AsyncMock()
    fake_llm.generate.return_value = GenerationResult(
        content="ok", model="custom", provider="llamacpp"
    )
    agent = CodeAgent(client=fake_llm, settings=settings)

    await agent.answer("...", intent="generate", force_model="llama-3-70b")

    assert fake_llm.generate.call_args.kwargs["model"] == "llama-3-70b"


@pytest.mark.asyncio
async def test_language_hint_propagated_in_user_message(settings: Settings) -> None:
    fake_llm = AsyncMock()
    fake_llm.generate.return_value = GenerationResult(content="...", model="x", provider="x")
    agent = CodeAgent(client=fake_llm, settings=settings)

    await agent.answer("hello world", intent="generate", language_hint="rust")

    user_msg = fake_llm.generate.call_args.args[0][1].content
    assert "[Language] rust" in user_msg
