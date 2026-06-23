"""Client Ollama async — backend LLM alternatif (route /api/chat).

Le backend par défaut de ZolaOS est `llama.cpp` via `LlamaCppClient` (format OpenAI
`/v1/chat/completions`). Ollama reste exposé pour le cas où on déploie en prod
Linux avec Ollama + ROCm/CUDA (sélection via `Settings.LLM_BACKEND="ollama"`).
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import orjson

from zolaos.core.logging import get_logger
from zolaos.core.metrics import LLM_CALL_DURATION_SECONDS, LLM_CALLS_TOTAL
from zolaos.llm.base import (
    GenerationOptions,
    GenerationResult,
    LLMClient,
    Message,
)

_log = get_logger("zolaos.llm.ollama")


class OllamaClient(LLMClient):
    """Client Ollama via HTTP (endpoint /api/chat)."""

    provider = "ollama"

    def __init__(self, host: str, timeout_seconds: int = 120) -> None:
        self._host = host.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OllamaClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        opts = options or GenerationOptions()
        payload = self._build_payload(messages, model, opts, stream=False)

        start = time.perf_counter()
        outcome = "error"
        try:
            r = await self._client.post("/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            outcome = "ok"
            duration = time.perf_counter() - start

            return GenerationResult(
                content=data.get("message", {}).get("content", ""),
                model=model,
                provider=self.provider,
                prompt_tokens=int(data.get("prompt_eval_count", 0)),
                completion_tokens=int(data.get("eval_count", 0)),
                duration_seconds=duration,
                metadata={"done_reason": str(data.get("done_reason", ""))},
            )
        finally:
            LLM_CALLS_TOTAL.labels(provider=self.provider, model=model, outcome=outcome).inc()
            LLM_CALL_DURATION_SECONDS.labels(provider=self.provider, model=model).observe(
                time.perf_counter() - start
            )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        opts = options or GenerationOptions()
        payload = self._build_payload(messages, model, opts, stream=True)

        start = time.perf_counter()
        outcome = "error"
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    chunk = orjson.loads(line)
                    if chunk.get("done"):
                        break
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
            outcome = "ok"
        finally:
            LLM_CALLS_TOTAL.labels(provider=self.provider, model=model, outcome=outcome).inc()
            LLM_CALL_DURATION_SECONDS.labels(provider=self.provider, model=model).observe(
                time.perf_counter() - start
            )

    @staticmethod
    def _build_payload(
        messages: list[Message],
        model: str,
        opts: GenerationOptions,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        ollama_opts: dict[str, Any] = {
            "temperature": opts.temperature,
            "top_p": opts.top_p,
            "num_predict": opts.max_tokens,
        }
        if opts.stop:
            ollama_opts["stop"] = list(opts.stop)
        if opts.seed is not None:
            ollama_opts["seed"] = opts.seed

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": ollama_opts,
        }
        if opts.json_mode:
            payload["format"] = "json"
        return payload
