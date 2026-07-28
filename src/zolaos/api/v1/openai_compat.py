"""Endpoint OpenAI-compatible `/v1/chat/completions` — surface MOTEUR.

Expose le routeur ZolaOS (modèle léger 8B, `make_router_client`) au format
`chat.completions` d'OpenAI, pour que des outils tiers (LangChain, Continue.dev,
Cursor, n'importe quel client "OpenAI-compatible") utilisent ZolaOS comme
fournisseur LLM sans adaptateur dédié (drop-in).

Ce router fait partie de la surface MOTEUR (comme `/v1/code`) : il ne porte
AUCUNE dépendance d'auth — c'est à l'orchestrateur de le monter avec les
dépendances adéquates selon le profil (box/cortex/engine).

Limites connues :
- **Streaming** (`stream=true`) : n'utilise pas `LLMClient.stream()` (token par
  token). On attend la génération complète puis on émet UN SEUL chunk SSE
  contenant tout le contenu, suivi du chunk final `finish_reason="stop"` et de
  `data: [DONE]`. Le client voit donc un flux SSE valide mais sans le vrai
  gain de latence perçue du token-par-token. Un futur lot pourra brancher
  `LLMClient.stream()` pour un streaming incrémental réel.
- **usage** (prompt_tokens/completion_tokens) : si le backend ne renseigne pas
  ces champs sur `GenerationResult` (ce qui est le cas de la plupart des
  clients locaux actuels), on les ESTIME grossièrement (~4 caractères/token).
  Ne pas s'y fier pour de la facturation précise.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Literal

import orjson
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from zolaos.core.settings import Settings, get_settings
from zolaos.llm.base import GenerationOptions, GenerationResult, Message
from zolaos.llm.factory import make_router_client

router = APIRouter(prefix="/v1", tags=["openai-compat"])


# --- Schémas d'entrée (sous-ensemble du format OpenAI) ----------------------


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(..., min_length=1)
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False


# --- Schémas de sortie (format OpenAI) --------------------------------------


class ChatCompletionMessageOut(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessageOut
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


def _estimate_tokens(text: str) -> int:
    """Estimation grossière (~4 caractères/token), utilisée seulement quand le
    backend ne renseigne pas `prompt_tokens`/`completion_tokens` (pas d'appel
    réseau, pas de tokenizer chargé — juste un ordre de grandeur)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _build_response(result: GenerationResult, messages: list[Message]) -> ChatCompletionResponse:
    prompt_text = "\n".join(m.content for m in messages)
    prompt_tokens = result.prompt_tokens or _estimate_tokens(prompt_text)
    completion_tokens = result.completion_tokens or _estimate_tokens(result.content)
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=result.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionMessageOut(role="assistant", content=result.content),
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


async def _sse_events(result: GenerationResult, model: str) -> AsyncIterator[bytes]:
    """Émet la réponse complète en un seul chunk SSE (cf. limite streaming en
    tête de module), puis le chunk final + `[DONE]` au format OpenAI."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    content_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": result.content},
                "finish_reason": None,
            }
        ],
    }
    yield b"data: " + orjson.dumps(content_chunk) + b"\n\n"

    final_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield b"data: " + orjson.dumps(final_chunk) + b"\n\n"
    yield b"data: [DONE]\n\n"


@router.post(
    "/chat/completions",
    response_model=None,
    summary="Endpoint OpenAI-compatible — ZolaOS comme fournisseur LLM drop-in",
)
async def chat_completions(
    body: ChatCompletionRequest,
    settings: Settings = Depends(get_settings),
) -> ChatCompletionResponse | StreamingResponse:
    """Traduit une requête `chat.completions` OpenAI vers le routeur ZolaOS.

    Aucune dépendance d'auth ici : l'orchestrateur monte ce router avec les
    garde-fous adéquats (cf. rapport de livraison du lot).
    """
    messages = [Message(role=m.role, content=m.content) for m in body.messages]
    model = body.model or settings.LLM_MODEL_ROUTER
    client = make_router_client(settings)
    options = GenerationOptions(temperature=body.temperature, max_tokens=body.max_tokens)
    result = await client.generate(messages, model=model, options=options)

    if not body.stream:
        return _build_response(result, messages)

    return StreamingResponse(
        _sse_events(result, model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
