"""Client llama.cpp / OpenAI-compatible — backend LLM par défaut de ZolaOS.

Parle au serveur `llama-server` (https://github.com/ggml-org/llama.cpp) via son
endpoint OpenAI-compatible `/v1/chat/completions`. Le même client fonctionne
avec n'importe quel serveur OpenAI-compatible local (vLLM, sglang, llama-server).
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

_log = get_logger("zolaos.llm.lcpp")

_SSE_PREFIX = b"data: "
_SSE_DONE = b"[DONE]"


class LlamaCppClient(LLMClient):
    """Client OpenAI-compatible pour llama-server (et compatibles)."""

    provider = "llamacpp"

    def __init__(self, host: str, timeout_seconds: int = 120, api_key: str | None = None) -> None:
        self._host = host.rstrip("/")
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=httpx.Timeout(timeout_seconds, connect=10.0),
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LlamaCppClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def health(self) -> bool:
        # llama-server expose /health (renvoie {"status":"ok"} ou 503 si modèle non chargé).
        try:
            r = await self._client.get("/health", timeout=5.0)
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
            r = await self._client.post("/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            outcome = "ok"
            duration = time.perf_counter() - start

            choice = (data.get("choices") or [{}])[0]
            usage = data.get("usage") or {}
            return GenerationResult(
                content=(choice.get("message") or {}).get("content", ""),
                model=data.get("model", model),
                provider=self.provider,
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                duration_seconds=duration,
                metadata={"finish_reason": str(choice.get("finish_reason", ""))},
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
            async with self._client.stream("POST", "/v1/chat/completions", json=payload) as r:
                r.raise_for_status()
                async for raw_line in r.aiter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.encode("utf-8") if isinstance(raw_line, str) else raw_line
                    if not line.startswith(_SSE_PREFIX):
                        continue
                    body = line[len(_SSE_PREFIX) :].strip()
                    if body == _SSE_DONE:
                        break
                    chunk = orjson.loads(body)
                    delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get(
                        "content", ""
                    )
                    if delta:
                        yield delta
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
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "temperature": opts.temperature,
            "top_p": opts.top_p,
            "max_tokens": opts.max_tokens,
        }
        if opts.stop:
            payload["stop"] = list(opts.stop)
        if opts.seed is not None:
            payload["seed"] = opts.seed
        if opts.json_mode:
            if opts.json_schema is not None:
                # Format OpenAI structured outputs : llama-server le convertit en
                # grammar GBNF stricte qui force le modèle à respecter le schéma.
                # Bien plus fiable que `json_object` seul, qui peut dériver sur
                # certaines requêtes (ex: "Rédige un contrat" → le modèle écrit
                # le contrat au lieu du JSON de routage).
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": opts.json_schema,
                        "strict": False,  # Pydantic peut générer pattern/default non strict-OpenAI
                    },
                }
            else:
                payload["response_format"] = {"type": "json_object"}
        return payload
