"""Découpage de texte en chunks pour ingestion RAG.

Stratégie : sliding window de tokens (compteur via le tokenizer du modèle
d'embeddings, par défaut bge-m3 → XLM-RoBERTa). Le découpage respecte la
limite de contexte du modèle d'embeddings ; l'overlap garantit qu'une
phrase à la frontière de deux chunks reste retrouvable dans au moins un.

Approche pragmatique pour le MVP Phase 2 : sliding window pur, sans
sentence-boundary aware. Affinage possible Phase 3+ si la qualité de retrieval
n'est pas suffisante (split sur paragraphes puis fallback token-based).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from zolaos.core.logging import get_logger
from zolaos.core.settings import get_settings

_log = get_logger("zolaos.rag.chunking")

_DEFAULT_TARGET_TOKENS = 512
_DEFAULT_OVERLAP_TOKENS = 64


@dataclass(frozen=True)
class Chunk:
    """Un chunk prêt pour embedding + indexation."""

    text: str
    index: int          # position dans le document source (0-based)
    tokens: int         # nombre de tokens (mesuré par le tokenizer)


class Chunker:
    def __init__(
        self,
        target_tokens: int = _DEFAULT_TARGET_TOKENS,
        overlap_tokens: int = _DEFAULT_OVERLAP_TOKENS,
        model: str | None = None,
    ) -> None:
        if overlap_tokens >= target_tokens:
            raise ValueError("overlap_tokens doit être strictement < target_tokens")
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.model_name = model or get_settings().EMBEDDING_MODEL
        self._tokenizer = None

    def _ensure_tokenizer(self) -> None:
        if self._tokenizer is not None:
            return
        from transformers import AutoTokenizer  # import retardé

        _log.info("chunker.loading_tokenizer", model=self.model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)

    def chunk(self, text: str) -> list[Chunk]:
        """Découpe `text` en chunks. Retourne liste vide si `text` vide."""
        if not text or not text.strip():
            return []
        self._ensure_tokenizer()
        assert self._tokenizer is not None  # noqa: S101

        encoded = self._tokenizer(text, add_special_tokens=False, return_tensors=None)
        ids = encoded["input_ids"]
        if len(ids) <= self.target_tokens:
            return [Chunk(text=text, index=0, tokens=len(ids))]

        chunks: list[Chunk] = []
        step = self.target_tokens - self.overlap_tokens
        i = 0
        idx = 0
        while i < len(ids):
            window = ids[i : i + self.target_tokens]
            chunk_text = self._tokenizer.decode(window, skip_special_tokens=True).strip()
            if chunk_text:
                chunks.append(Chunk(text=chunk_text, index=idx, tokens=len(window)))
                idx += 1
            i += step
        return chunks


@lru_cache(maxsize=1)
def get_chunker() -> Chunker:
    return Chunker()
