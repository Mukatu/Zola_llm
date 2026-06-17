"""Service d'embedding (bge-m3) — chargement lazy, batching, wrappers sync + async.

Le modèle est chargé au premier appel et conservé en mémoire (singleton via
`get_embedding_service()`). sentence-transformers est synchrone et CPU/GPU
bloquant, donc les méthodes async délèguent à `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import numpy as np

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings, get_settings

_log = get_logger("zolaos.rag.embeddings")

_DEFAULT_BATCH = 32


class EmbeddingService:
    def __init__(self, settings: Settings, batch_size: int = _DEFAULT_BATCH) -> None:
        self._settings = settings
        self._batch_size = batch_size
        self._model = None  # chargement lazy

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # import retardé

        _log.info(
            "embedding.loading",
            model=self._settings.EMBEDDING_MODEL,
            device=self._settings.EMBEDDING_DEVICE,
        )
        self._model = SentenceTransformer(
            self._settings.EMBEDDING_MODEL,
            device=self._settings.EMBEDDING_DEVICE,
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode une liste de textes. Retourne des vecteurs `EMBEDDING_DIMENSION`.

        Normalise (cosine-ready). Gère le batching interne via sentence-transformers.
        """
        self._ensure_loaded()
        assert self._model is not None  # noqa: S101
        vectors: np.ndarray = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]

    async def aencode(self, texts: list[str]) -> list[list[float]]:
        """Variante async — déporte l'encodage CPU/GPU dans un thread."""
        return await asyncio.to_thread(self.encode, texts)

    async def aencode_one(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.encode_one, text)


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(settings=get_settings())
