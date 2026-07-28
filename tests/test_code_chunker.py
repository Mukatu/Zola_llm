"""Tests du CodeChunker (chunking par symboles de haut niveau).

Le tokenizer réel (bge-m3 / XLM-RoBERTa via `transformers`) est lourd à charger
et indisponible hors-réseau en CI. On injecte donc un `Chunker` fallback dont
le `_tokenizer` est déjà peuplé par un faux tokenizer (comptage par mots), ce
qui court-circuite `_ensure_tokenizer()` (no-op si `_tokenizer is not None`)
sans jamais toucher au réseau ni à `transformers`.
"""

from __future__ import annotations

import re

from zolaos.rag.chunking import Chunker
from zolaos.rag.chunking_specialized import CHUNKER_REGISTRY, CodeChunker


class _FakeTokenizer:
    """Tokenizer factice : 1 mot = 1 token. Suffisant pour tester la logique
    de découpage/regroupement sans dépendre d'un vrai modèle."""

    def __call__(self, text: str, add_special_tokens: bool = False, return_tensors=None):
        return {"input_ids": text.split()}

    def decode(self, ids, skip_special_tokens: bool = True) -> str:
        return " ".join(ids)


def _fake_fallback(target_tokens: int, overlap_tokens: int) -> Chunker:
    fb = Chunker(target_tokens=target_tokens, overlap_tokens=overlap_tokens)
    fb._tokenizer = _FakeTokenizer()  # court-circuite _ensure_tokenizer (réseau)
    return fb


# 3 symboles de haut niveau : 15, 12 et 14 "mots" (mesurés) respectivement.
# target_tokens=15 : chacun tient seul, mais deux consécutifs (>= 26) dépassent
# toujours → aucun regroupement, un chunk par symbole.
PY_SOURCE = """\
def premiere_fonction(a, b):
    total = a + b
    for i in range(total):
        print(i)
    return total


def deuxieme_fonction(x):
    if x > 0:
        return x * 2
    return 0


class MaClasse:
    def __init__(self, valeur):
        self.valeur = valeur

    def double(self):
        return self.valeur * 2
"""

# 2 symboles de 25 et 24 "mots" ; target_tokens=30 : chacun tient seul, la
# somme (49) dépasse → pas de regroupement.
JS_SOURCE = """\
function maFonction(a, b) {
    let total = a + b;
    for (let i = 0; i < total; i++) {
        console.log(i);
    }
    return total;
}

const maConstArrow = (x, y) => {
    const somme = x + y;
    const produit = x * y;
    return somme + produit;
};
"""

NO_SYMBOL_SOURCE = """\
# fichier de configuration
timeout: 30
retries: 5
endpoint: https://example.invalid/api
niveau_log: info
cache_active: true
"""


def test_python_one_chunk_per_symbol():
    fallback = _fake_fallback(target_tokens=15, overlap_tokens=2)
    chunker = CodeChunker(target_tokens=15, overlap_tokens=2, fallback=fallback, language="python")

    chunks = chunker.chunk(PY_SOURCE)

    assert len(chunks) == 3
    symboles = [re.search(r"# symbole: (\w+)", c.text).group(1) for c in chunks]
    assert symboles == ["premiere_fonction", "deuxieme_fonction", "MaClasse"]
    for c in chunks:
        assert c.text.startswith("# symbole:")
    # Le corps de la classe (avec ses méthodes) est bien capturé dans son chunk.
    assert "def double" in chunks[2].text


def test_python_file_path_header_and_registry():
    fallback = _fake_fallback(target_tokens=15, overlap_tokens=2)
    chunker = CodeChunker(
        target_tokens=15,
        overlap_tokens=2,
        fallback=fallback,
        language="python",
        file_path="src/exemple/module.py",
    )

    chunks = chunker.chunk(PY_SOURCE)

    assert len(chunks) == 3
    assert all(c.text.startswith("# fichier: src/exemple/module.py") for c in chunks)
    # Le chunker `code` doit être sélectionnable depuis le manifeste/CLI.
    assert CHUNKER_REGISTRY["code"] is CodeChunker


def test_js_function_and_arrow_const_detected():
    fallback = _fake_fallback(target_tokens=30, overlap_tokens=2)
    chunker = CodeChunker(
        target_tokens=30, overlap_tokens=2, fallback=fallback, language="javascript"
    )

    chunks = chunker.chunk(JS_SOURCE)

    assert len(chunks) == 2
    symboles = [re.search(r"# symbole: (\w+)", c.text).group(1) for c in chunks]
    assert symboles == ["maFonction", "maConstArrow"]


def test_small_fragments_are_grouped():
    # 2 lignes d'import + 4 petites fonctions (4 "mots" chacune) : avec un
    # target_tokens généreux, tout doit être regroupé dans UN seul chunk
    # plutôt qu'éclaté en 5 micro-chunks (imports + a + b + c + d).
    source = """\
import os
import sys


def a():
    return 1


def b():
    return 2


def c():
    return 3


def d():
    return 4
"""
    fallback = _fake_fallback(target_tokens=200, overlap_tokens=2)
    chunker = CodeChunker(target_tokens=200, overlap_tokens=2, fallback=fallback, language="python")

    chunks = chunker.chunk(source)

    assert len(chunks) == 1
    # 1 entête `# symbole:` par fragment regroupé (prélude d'imports + a/b/c/d).
    assert chunks[0].text.count("# symbole:") == 5
    assert "# symbole: prélude" in chunks[0].text
    for name in ("a", "b", "c", "d"):
        assert f"# symbole: {name}" in chunks[0].text


def test_no_symbol_falls_back_to_generic_chunker():
    fallback = _fake_fallback(target_tokens=20, overlap_tokens=2)
    chunker = CodeChunker(target_tokens=20, overlap_tokens=2, fallback=fallback, language="python")

    chunks = chunker.chunk(NO_SYMBOL_SOURCE)
    expected = fallback.chunk(NO_SYMBOL_SOURCE)

    assert chunks == expected
    assert all(not c.text.startswith("# symbole:") for c in chunks)


def test_too_short_text_falls_back_to_generic_chunker():
    # Contient bien un symbole (`def f`), mais le fichier est trop court
    # (4 "mots") : on ne s'embête pas à découper par symbole.
    fallback = _fake_fallback(target_tokens=200, overlap_tokens=2)
    chunker = CodeChunker(target_tokens=200, overlap_tokens=2, fallback=fallback, language="python")

    short_source = "def f():\n    return 1\n"
    chunks = chunker.chunk(short_source)
    expected = fallback.chunk(short_source)

    assert chunks == expected


def test_empty_text_returns_empty_list():
    fallback = _fake_fallback(target_tokens=200, overlap_tokens=2)
    chunker = CodeChunker(target_tokens=200, overlap_tokens=2, fallback=fallback)

    assert chunker.chunk("") == []
    assert chunker.chunk("   \n  ") == []


def test_unknown_extension_generic_detection_still_finds_python_symbols():
    # Pas de `language` explicite, extension inconnue : la détection générique
    # (toutes les heuristiques langages combinées) doit quand même trouver
    # les symboles Python.
    fallback = _fake_fallback(target_tokens=15, overlap_tokens=2)
    chunker = CodeChunker(
        target_tokens=15, overlap_tokens=2, fallback=fallback, file_path="script.weird"
    )

    chunks = chunker.chunk(PY_SOURCE)

    assert len(chunks) == 3


def test_oversized_symbol_is_split_via_fallback_but_keeps_symbol_header():
    # Une seule fonction, plus grosse que target_tokens : doit être redécoupée
    # via le fallback générique en plusieurs chunks, chacun gardant l'entête
    # `# symbole:` de la fonction d'origine.
    source = "def grosse_fonction():\n" + "\n".join(f"    x{i} = {i}" for i in range(40))
    fallback = _fake_fallback(target_tokens=10, overlap_tokens=1)
    chunker = CodeChunker(target_tokens=10, overlap_tokens=1, fallback=fallback, language="python")

    chunks = chunker.chunk(source)

    assert len(chunks) > 1
    assert all(c.text.startswith("# symbole: grosse_fonction") for c in chunks)
