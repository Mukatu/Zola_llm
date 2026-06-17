"""Factory de clients LLM — fait le bon choix selon le backend + le flag fallback.

Deux dimensions :
- backend local : `llamacpp` (défaut, OpenAI-compatible) ou `ollama` (route /api/chat)
- routage modèle : `router_client` (8B port 11434) vs `core_client` (70B port 11435)

Le fallback externe (Anthropic) reste désactivé par défaut via guard.
"""

from __future__ import annotations

from zolaos.core.settings import Settings
from zolaos.llm.base import LLMClient
from zolaos.llm.external_client import ExternalLLMClient
from zolaos.llm.lcpp_client import LlamaCppClient
from zolaos.llm.ollama_client import OllamaClient


def _make_local(host: str, settings: Settings) -> LLMClient:
    """Instancie le bon client local selon le backend configuré."""
    api_key = settings.LLM_API_KEY.get_secret_value() or None
    if settings.LLM_BACKEND == "ollama":
        # Ollama ignore l'API key (pas de bearer auth natif).
        return OllamaClient(host=host, timeout_seconds=settings.LLM_TIMEOUT_SECONDS)
    return LlamaCppClient(
        host=host,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        api_key=api_key,
    )


def make_router_client(settings: Settings) -> LLMClient:
    """Client pour le routeur + brigade (modèle léger 8B, port 11434 par défaut)."""
    return _make_local(settings.LLM_HOST_ROUTER, settings)


def make_core_client(settings: Settings) -> LLMClient:
    """Client pour le méta-agent Planning (modèle lourd 70B, port 11435 par défaut)."""
    return _make_local(settings.LLM_HOST_CORE, settings)


def make_external_client(settings: Settings) -> ExternalLLMClient:
    """Retourne le client externe. L'instanciation NE déclenche PAS le guard
    (le guard se déclenche à l'usage). Le client lui-même refuse tout appel
    tant que le flag est OFF.
    """
    return ExternalLLMClient(settings=settings)


def pick_client(settings: Settings, *, prefer_external: bool = False) -> LLMClient:
    """Choix par défaut : routeur local. Externe uniquement si flag ON ET demandé."""
    if prefer_external and settings.ENABLE_EXTERNAL_FALLBACK:
        return make_external_client(settings)
    return make_router_client(settings)
