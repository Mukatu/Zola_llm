"""Traduction de contrats — service LLM (client mocké) + validation endpoint."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from zolaos.agents.legal.translation import TranslationService, decouper
from zolaos.api.v1.legal import TranslateIn, _texte_depuis
from zolaos.core.settings import Settings


class _FakeGen:
    def __init__(self, content: str) -> None:
        self.content = content
        self.model = "llama-3-8b"
        self.duration_seconds = 0.0


class _FakeClient:
    async def generate(self, messages, *, model, options):  # type: ignore[no-untyped-def]
        system = messages[0].content
        if "identifies la langue" in system:
            return _FakeGen("anglais")
        return _FakeGen("TRAD[" + messages[-1].content[:15] + "]")


def _settings() -> Settings:
    return Settings(
        APP_ENV="dev",
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
    )


def test_decouper_respecte_les_blocs() -> None:
    texte = "\n\n".join("para " * 100 for _ in range(6))  # ~3000+ car.
    blocs = decouper(texte, taille=1000)
    assert len(blocs) >= 2
    assert "".join(blocs).replace("\n\n", "") == texte.replace("\n\n", "")


def test_decouper_texte_court() -> None:
    assert decouper("court") == ["court"]


async def test_detect_language() -> None:
    svc = TranslationService(_FakeClient(), _settings())  # type: ignore[arg-type]
    assert await svc.detect_language("Hello, this is an English contract.") == "anglais"


async def test_translate_concatene_les_blocs() -> None:
    svc = TranslationService(_FakeClient(), _settings())  # type: ignore[arg-type]
    res = await svc.translate("Article 1. This agreement...")
    assert res.source_lang == "anglais"
    assert res.target_lang == "français"
    assert res.text.startswith("TRAD[")


def test_texte_depuis_requiert_une_source() -> None:
    with pytest.raises(HTTPException) as exc:
        _texte_depuis(TranslateIn())
    assert exc.value.status_code == 422


def test_texte_depuis_text() -> None:
    texte, titre = _texte_depuis(TranslateIn(text="Hello"))
    assert texte == "Hello"
    assert titre is None
