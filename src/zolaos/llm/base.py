"""Interface unifiée des clients LLM (local Ollama + fallback externe)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Message:
    """Message dans une conversation LLM."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class GenerationOptions:
    """Paramètres de génération communs.

    `json_mode=True` force une sortie JSON. Si `json_schema` est fourni en
    plus, le backend doit contraindre la sortie à respecter le schéma (via
    grammar GBNF dérivée pour llama.cpp, ou response_format pour OpenAI).
    """

    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 1024
    stop: tuple[str, ...] = ()
    seed: int | None = None
    json_mode: bool = False
    json_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationResult:
    """Résultat d'une génération LLM."""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient(ABC):
    """Contrat commun à tous les clients LLM.

    Implémentations :
    - LlamaCppClient (local, par défaut — OpenAI-compatible /v1/chat/completions)
    - OllamaClient (local, alternatif — route /api/chat, pour prod Linux Ollama)
    - ExternalLLMClient (Anthropic, désactivé par le guard tant que flag OFF)
    """

    provider: str  # "llamacpp" | "ollama" | "external"

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> GenerationResult:
        """Génération non-streamée."""

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]:
        """Génération streamée (yield chunks de texte)."""

    @abstractmethod
    async def health(self) -> bool:
        """True si le backend répond."""
