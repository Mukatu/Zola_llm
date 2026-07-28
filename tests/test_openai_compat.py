"""Tests endpoint OpenAI-compatible `/v1/chat/completions` (surface MOTEUR).

Router monté seul sur une app FastAPI de test (pas de Redis/Postgres/RAG) —
le client LLM est mocké via `make_router_client` : aucun réseau, aucun modèle
chargé.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from zolaos.api.v1.openai_compat import router
from zolaos.core.settings import Settings, get_settings
from zolaos.llm.base import GenerationResult, Message


def _settings() -> Settings:
    return Settings(
        POSTGRES_PASSWORD_APP="x", POSTGRES_PASSWORD_MIGRATIONS="x", JWT_SECRET="x" * 32
    )


@dataclass
class _FakeLLMClient:
    """Faux client LLM : renvoie toujours le même GenerationResult, sans réseau."""

    provider: str = "llamacpp"

    async def generate(
        self, messages: list[Message], *, model: str, options=None
    ) -> GenerationResult:
        return GenerationResult(content="Bonjour", model="llama-3-8b", provider="llamacpp")


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = _settings
    return app


async def test_chat_completions_returns_openai_format(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "zolaos.api.v1.openai_compat.make_router_client", lambda settings: _FakeLLMClient()
    )

    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "salut"}]},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Bonjour"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["model"] == "llama-3-8b"
    assert "usage" in body
    assert body["usage"]["total_tokens"] >= 0


async def test_chat_completions_streaming_emits_sse_done(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "zolaos.api.v1.openai_compat.make_router_client", lambda settings: _FakeLLMClient()
    )

    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "salut"}], "stream": True},
        )

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "chat.completion.chunk" in r.text
    assert "Bonjour" in r.text
    assert r.text.strip().endswith("data: [DONE]")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
