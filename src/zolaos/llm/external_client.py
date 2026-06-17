"""Client LLM externe (Anthropic) — désactivé par défaut par le guard.

Toute instanciation et tout appel passent obligatoirement par
`ensure_external_fallback_allowed`. Tant que `ENABLE_EXTERNAL_FALLBACK=false`,
ce module n'effectue **aucune** requête réseau.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from zolaos.core.logging import get_logger
from zolaos.core.metrics import LLM_CALL_DURATION_SECONDS, LLM_CALLS_TOTAL
from zolaos.core.settings import Settings
from zolaos.llm.base import (
    GenerationOptions,
    GenerationResult,
    LLMClient,
    Message,
)
from zolaos.llm.guard import ensure_external_fallback_allowed

_log = get_logger("zolaos.llm.external")


class ExternalLLMClient(LLMClient):
    """Stub Anthropic. Lève `ExternalFallbackDisabledError` tant que le flag est OFF.

    Le client réel (SDK anthropic) n'est instancié qu'au premier appel autorisé,
    pour éviter toute initialisation de transport HTTP quand le fallback est OFF.
    """

    provider = "external"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # type: ignore[var-annotated]  # initialisé à la demande

    def _ensure_ready(self, caller: str) -> None:
        ensure_external_fallback_allowed(self._settings, caller=caller)
        if self._client is None:
            # Import retardé : pas même chargé en mémoire tant que flag OFF.
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=self._settings.ANTHROPIC_API_KEY.get_secret_value()
            )

    async def health(self) -> bool:
        # Le health check ne déclenche PAS le guard : il retourne simplement False
        # quand le fallback est désactivé. Comportement attendu pour `/health`.
        if not self._settings.ENABLE_EXTERNAL_FALLBACK:
            return False
        # En mode actif, on considère le SDK comme up tant qu'il s'instancie.
        try:
            self._ensure_ready(caller="health")
        except Exception:  # noqa: BLE001
            return False
        return True

    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        self._ensure_ready(caller="generate")
        opts = options or GenerationOptions()

        system_prompts = [m.content for m in messages if m.role == "system"]
        chat_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        start = time.perf_counter()
        outcome = "error"
        try:
            assert self._client is not None  # noqa: S101
            response = await self._client.messages.create(
                model=model,
                system="\n\n".join(system_prompts) if system_prompts else "",
                messages=chat_messages,
                max_tokens=opts.max_tokens,
                temperature=opts.temperature,
                top_p=opts.top_p,
            )
            outcome = "ok"
            duration = time.perf_counter() - start

            text = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
            return GenerationResult(
                content=text,
                model=model,
                provider=self.provider,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                duration_seconds=duration,
                metadata={"stop_reason": str(response.stop_reason)},
            )
        finally:
            LLM_CALLS_TOTAL.labels(
                provider=self.provider, model=model, outcome=outcome
            ).inc()
            LLM_CALL_DURATION_SECONDS.labels(
                provider=self.provider, model=model
            ).observe(time.perf_counter() - start)

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        self._ensure_ready(caller="stream")
        # Implémentation streaming différée — non requise en Phase 1.
        result = await self.generate(messages, model=model, options=options)
        yield result.content
